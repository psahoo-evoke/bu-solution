import { Component, DestroyRef, ElementRef, HostListener, OnInit, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';
import { ApiService } from '../api/api.service';
import { StudentNotification } from '../api/models';

/** How often the bell checks for new notifications while the tab is visible. */
export const POLL_MS = 60_000;

/**
 * A signed-in student's in-app notifications (GET /students/{id}/notifications): a bell with the unread count in the
 * top bar and a panel listing them, newest first. Opening the panel marks them read on the server (POST …/seen);
 * the items that were new stay highlighted until the panel closes. Refreshes on navigation and every minute while
 * the tab is visible. Text is interpolated, never bound as HTML.
 */
@Component({
  selector: 'app-notification-bell',
  imports: [DatePipe],
  template: `
    <div class="bell">
      <button type="button" class="bell__button" [attr.aria-expanded]="open()" aria-controls="bell-panel"
              [attr.aria-label]="unread() ? 'Notifications, ' + unread() + ' unread' : 'Notifications'"
              (click)="toggle()">
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor"
          d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm7-6V11a7 7 0 0 0-5.5-6.84V3a1.5 1.5 0 0 0-3 0v1.16A7 7 0 0 0 5 11v5l-2 2v1h18v-1z"/></svg>
        @if (unread()) { <span class="bell__badge" aria-hidden="true">{{ unread() > 9 ? '9+' : unread() }}</span> }
      </button>
      @if (open()) {
        <section id="bell-panel" class="bell__panel" role="dialog" aria-label="Notifications">
          <header class="bell__head">
            <strong>Notifications</strong>
            @if (newIds().size) { <span class="muted small">{{ newIds().size }} new</span> }
          </header>
          @if (error()) {
            <p class="bell__empty">{{ error() }}</p>
          } @else if (!items().length) {
            <p class="bell__empty">No notifications yet. You will see updates here when your transcript is read, a syllabus
              is needed, and a course is decided or posted.</p>
          } @else {
            <ul class="bell__list">
              @for (n of items(); track n.id) {
                <li class="bell__item bell__item--{{ n.kind }}" [class.is-new]="newIds().has(n.id)">
                  <button type="button" (click)="go()">
                    <span class="bell__title">{{ n.title }}</span>
                    <span class="bell__body">{{ n.body }}</span>
                    <span class="bell__time">{{ n.at | date: 'd MMM y, HH:mm' }}</span>
                  </button>
                </li>
              }
            </ul>
          }
        </section>
      }
    </div>
  `,
})
export class NotificationBell implements OnInit {
  readonly studentId = input.required<string>();
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly host = inject(ElementRef<HTMLElement>);

  protected readonly items = signal<StudentNotification[]>([]);
  protected readonly unread = signal(0);
  protected readonly open = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Unread when the panel was opened: highlighted while it stays open, although they are now marked read. */
  protected readonly newIds = signal<Set<string>>(new Set());
  /** Bumped by every request: an answer to an older request (a page-load refresh still on its way when the panel
   * was opened) must not overwrite a newer one, such as the read state after opening. */
  private version = 0;

  constructor() {
    const timer = setInterval(() => {
      if (typeof document === 'undefined' || !document.hidden) this.load();
    }, POLL_MS);
    const nav = this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => this.load());
    inject(DestroyRef).onDestroy(() => {
      clearInterval(timer);
      nav.unsubscribe();
    });
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const v = ++this.version;
    this.api.getNotifications(this.studentId()).subscribe({
      next: (r) => {
        if (v !== this.version) return;
        this.items.set(r.items);
        this.unread.set(r.unread);
        this.error.set(null);
      },
      error: () => this.error.set('Notifications could not be loaded.'),
    });
  }

  toggle(): void {
    if (this.open()) {
      this.close();
      return;
    }
    this.newIds.set(new Set(this.items().filter((n) => n.unread).map((n) => n.id)));
    this.open.set(true);
    const before = this.unread();
    if (before) {
      const v = ++this.version;
      this.unread.set(0);                   // the student is looking at them now: clear the badge at once
      this.api.markNotificationsSeen(this.studentId()).subscribe({
        next: (r) => {
          if (v !== this.version) return;
          this.items.set(r.items);
          this.unread.set(r.unread);
        },
        error: () => {
          if (v === this.version) this.unread.set(before);    // not saved: still unread, the next open tries again
        },
      });
    }
  }

  close(): void {
    this.open.set(false);
    this.newIds.set(new Set());
  }

  go(): void {
    this.close();
    void this.router.navigate(['/student', this.studentId()]);
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.open()) this.close();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.host.nativeElement.contains(event.target as Node)) this.close();
  }
}
