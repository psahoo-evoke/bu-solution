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
  protected readonly tab = signal<'chat' | 'form'>('chat');
  protected readonly schools = signal<CreditSchool[]>([]);
  protected readonly suggestions = [
    'Will NYU PSYCH-UA 1 transfer to BU?',
    'I got a C- in NYU MATH-UA 121. Does it count?',
    'What could NYU PSYCH-UA 10 be at BU?',
    'Which schools can I ask about?',
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
    this.api.creditSchools().subscribe({ next: (s) => this.schools.set(s), error: () => undefined });
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
