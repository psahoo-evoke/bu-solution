import { Component, ElementRef, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { ApiService } from '../api/api.service';
import { ChatTurn, CreditCheckResult, CreditCourse, CreditKind, CreditSchool } from '../api/models';

/** Shown under each assistant reply / form result: facts straight from the rules engine, not the model's prose. */
interface ChatEntry extends ChatTurn {
  results?: CreditCheckResult[];
}

export const KIND_LABEL: Record<CreditKind, string> = {
  decided_equivalent: 'Already decided',
  decided_elective: 'Already decided – elective',
  not_transferable: 'Not transferable',
  pending_review: 'Needs review',
  needs_evaluation: 'Needs evaluation',
  unknown_school: 'School not in catalog',
  unknown_course: 'Course not in catalog',
};

/** Colour family of a result: words always come first, colour and icon are secondary cues. */
export type CreditTone = 'good' | 'warn' | 'bad' | 'info';
export const KIND_TONE: Record<CreditKind, CreditTone> = {
  decided_equivalent: 'good',
  decided_elective: 'good',
  not_transferable: 'bad',
  pending_review: 'warn',
  needs_evaluation: 'warn',
  unknown_school: 'info',
  unknown_course: 'info',
};
/** Inner stroke of the round status icon (drawn inside a 24x24 circle). */
export const TONE_ICON: Record<CreditTone, string> = {
  good: 'm8.5 12.2 2.4 2.4 4.6-4.9',
  warn: 'M12 7v5l3.2 1.9',
  bad: 'm15 9-6 6M9 9l6 6',
  info: 'M9.4 9.2a2.7 2.7 0 0 1 5.2.9c0 1.8-2.6 2.4-2.6 2.4M12 16.6h.01',
};

/** 'psych-ua10' and 'PSYCH-UA 10' are the same course code. */
export function normCode(code: string): string {
  return code.toUpperCase().replace(/\s+/g, '');
}

/** Keep the last turns the API accepts (12), starting with a user turn. */
export function trimHistory(turns: ChatTurn[], max = 12): ChatTurn[] {
  let out = turns.slice(-max);
  while (out.length && out[0].role !== 'user') out = out.slice(1);
  return out;
}

/** Public page (no sign-in): "Will my course transfer?" as a chat and as a quick form. Nothing is stored. */
@Component({
  selector: 'app-credit-check',
  imports: [FormsModule, NgTemplateOutlet, RouterLink],
  templateUrl: './credit-check.html',
  styleUrl: './credit-check.scss',
})
export class CreditCheckPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly log = viewChild<ElementRef<HTMLElement>>('log');
  private readonly composer = viewChild<ElementRef<HTMLTextAreaElement>>('composer');

  protected kindLabel(kind: string): string {
    return KIND_LABEL[kind as CreditKind] ?? kind;
  }
  protected kindTone(kind: string): CreditTone {
    return KIND_TONE[kind as CreditKind] ?? 'info';
  }
  protected toneIcon(tone: CreditTone): string {
    return TONE_ICON[tone];
  }
  protected readonly tab = signal<'chat' | 'form'>('chat');
  protected readonly schools = signal<CreditSchool[]>([]);
  protected readonly schoolsState = signal<'loading' | 'ready' | 'error'>('loading');
  /** The side panel lists a handful of schools; the rest are counted, not listed. */
  protected readonly shownSchools = computed(() => this.schools().slice(0, 8));
  protected readonly moreSchools = computed(() => Math.max(0, this.schools().length - 8));
  protected readonly suggestions = [
    { label: 'Check a course', text: 'Will NYU PSYCH-UA 1 transfer to BU?', icon: 'M20 20l-4-4M11 17a6 6 0 1 1 0-12 6 6 0 0 1 0 12z' },
    { label: 'Does my grade count?', text: 'I got a C- in NYU MATH-UA 121. Does it count?', icon: 'M12 14a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM8.6 12.8 7.5 21l4.5-2.5 4.5 2.5-1.1-8.2' },
    { label: 'Not decided yet?', text: 'What could NYU PSYCH-UA 10 be at BU?', icon: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V15h7v-1.1A6 6 0 0 0 12 3z' },
    { label: 'What is covered', text: 'Which schools can I ask about?', icon: 'M3 21h18M5 21V9l7-5 7 5v12M9.5 21v-5h5v5' },
  ];
  /** "What the answers mean": one entry per tone, in the order a student hopes for. */
  protected readonly legend: { tone: CreditTone; label: string; text: string }[] = [
    { tone: 'good', label: 'Already decided', text: 'BU has ruled on this course before, so you will most likely get the same credit.' },
    { tone: 'warn', label: 'Needs evaluation', text: 'No decision yet. An evaluator reviews it; you see a preliminary estimate.' },
    { tone: 'bad', label: 'Not transferable', text: 'BU has decided this course does not earn credit.' },
    { tone: 'info', label: 'Not in the catalog', text: 'The school or course is new to us. Check the code or describe what it covers.' },
  ];

  // chat
  protected readonly turns = signal<ChatEntry[]>([]);
  protected readonly sending = signal(false);
  protected readonly chatError = signal<string | null>(null);
  protected draft = '';

  // form
  protected school = '';
  protected readonly courseCode = signal('');
  protected covers = '';
  /** The chosen school's catalog courses (course picker); loaded once per school. */
  protected readonly courses = signal<CreditCourse[]>([]);
  protected readonly loadingCourses = signal(false);
  private readonly courseCache = new Map<string, CreditCourse[]>();
  /** The typed code is not one of the school's catalog courses: ask what it covers so it can still be estimated. */
  protected readonly unlisted = computed(() => {
    const code = normCode(this.courseCode());
    return !!code && !this.loadingCourses() && !this.courses().some((c) => normCode(c.course_code) === code);
  });
  protected readonly codePlaceholder = computed(() => this.courses()[0]?.course_code ?? 'PSYCH-UA 10');
  protected grade = '';
  protected term = '';
  protected readonly checking = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly result = signal<CreditCheckResult | null>(null);

  ngOnInit(): void {
    this.api.creditSchools().subscribe({
      next: (s) => {
        this.schools.set(s);
        this.schoolsState.set('ready');
      },
      error: () => this.schoolsState.set('error'),
    });
  }

  protected ask(text?: string): void {
    const content = (text ?? this.draft).trim();
    if (!content || this.sending()) return;
    if (content.length > 600) {
      this.chatError.set('Please keep a message under 600 characters.');
      return;
    }
    this.draft = '';
    this.autoGrow();
    this.chatError.set(null);
    this.turns.update((t) => [...t, { role: 'user', content }]);
    this.sending.set(true);
    this.scroll();
    const history = trimHistory(this.turns().map(({ role, content: c, signature }) => ({ role, content: c, signature })));
    this.api.creditChat(history).subscribe({
      next: (r) => {
        this.turns.update((t) => [...t, { role: 'assistant', content: r.reply, signature: r.signature, results: r.results }]);
        this.sending.set(false);
        this.scroll();
        this.focusComposer();
      },
      error: (err: unknown) => {
        this.sending.set(false);
        const status = err instanceof HttpErrorResponse ? err.status : 0;
        const detail = err instanceof HttpErrorResponse ? (err.error?.detail as string | undefined) : undefined;
        if (status === 503) {
          this.formError.set('The chat is not available right now. Use this quick check instead.');
          this.tab.set('form');
        } else {
          this.chatError.set(detail || 'The chat could not answer. Please try again or use the quick check.');
          this.focusComposer();
        }
      },
    });
  }

  /** New school: clear the course and load that school's catalog courses (cached for the visit). */
  protected onSchool(school: string): void {
    this.school = school;
    this.courseCode.set('');
    this.covers = '';
    this.result.set(null);
    const cached = this.courseCache.get(school);
    if (cached) {
      this.courses.set(cached);
      return;
    }
    this.courses.set([]);
    this.loadingCourses.set(true);
    this.api.creditCourses(school).subscribe({
      next: (rows) => {
        this.courseCache.set(school, rows);
        if (this.school === school) this.courses.set(rows);
        this.loadingCourses.set(false);
      },
      error: () => this.loadingCourses.set(false),       // the field stays free text
    });
  }

  protected check(): void {
    if (!this.school || !this.courseCode().trim() || this.checking()) {
      this.formError.set('Choose a school and enter the course code.');
      return;
    }
    this.formError.set(null);
    this.checking.set(true);
    this.api
      .creditCheck({ school: this.school, course_code: this.courseCode().trim(), grade: this.grade || undefined,
                     term: this.term.trim() || undefined,
                     description: (this.unlisted() && this.covers.trim()) || undefined })
      .subscribe({
        next: (r) => {
          this.result.set(r);
          this.checking.set(false);
        },
        error: (err: unknown) => {
          this.checking.set(false);
          const detail = err instanceof HttpErrorResponse ? (err.error?.detail as unknown) : undefined;
          this.formError.set(typeof detail === 'string' ? detail : 'Check the course code (e.g. PSYCH-UA 10) and term (e.g. Fall 2024).');
        },
      });
  }

  protected onKey(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.ask();
    }
  }

  /** A suggested course from a result card: ask about it in the chat, or check it in the form. */
  protected pickCourse(r: CreditCheckResult, code: string): void {
    if (this.tab() === 'chat') {
      this.ask(`${r.school_code} ${code}`);
    } else {
      this.courseCode.set(code);
      this.check();
    }
  }

  /** A suggested school (chat only: the form picks schools from a list). */
  protected pickSchool(name: string): void {
    this.ask(`I mean ${name}`);
  }

  /** A school from the side panel: start the question in the chat, or choose it in the form. */
  protected useSchool(s: CreditSchool): void {
    if (this.tab() === 'form') {
      this.onSchool(s.school_code);
      return;
    }
    this.draft = `Will ${s.school_code} `;
    this.autoGrow();
    setTimeout(() => {
      const el = this.composer()?.nativeElement;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    });
  }

  /** Start over: the conversation only lives in this page, so clearing it forgets everything. */
  protected newChat(): void {
    this.turns.set([]);
    this.chatError.set(null);
    this.draft = '';
    this.autoGrow();
    this.focusComposer();
  }

  /** The composer grows with its text up to about six lines, then scrolls. */
  protected autoGrow(): void {
    setTimeout(() => {
      const el = this.composer()?.nativeElement;
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    });
  }

  private focusComposer(): void {
    setTimeout(() => this.composer()?.nativeElement.focus());
  }

  private scroll(): void {
    setTimeout(() => {
      const el = this.log()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
