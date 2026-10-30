import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentNotification } from '../api/models';
import { NotificationBell } from './notification-bell';

const URL = '/api/students/SYN-24001/notifications';
const n = (id: string, unread: boolean, kind: StudentNotification['kind'] = 'syllabus_request'): StudentNotification => ({
  id, kind, title: `Title ${id}`, body: `Body ${id}`, at: '2026-10-30T09:15:00+00:00', ext_id: null, unread,
});

async function setup(items: StudentNotification[]) {
  TestBed.configureTestingModule({
    imports: [NotificationBell],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(NotificationBell);
  fixture.componentRef.setInput('studentId', 'SYN-24001');
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne(URL).flush({ items, unread: items.filter((i) => i.unread).length, seen_at: null });
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, http, el: fixture.nativeElement as HTMLElement };
}

describe('NotificationBell', () => {
  it('shows the unread count and marks everything read when opened, keeping the new ones highlighted', async () => {
    const { fixture, http, el } = await setup([n('a', true), n('b', false, 'transcript')]);
    const button = el.querySelector('.bell__button') as HTMLButtonElement;
    expect(el.querySelector('.bell__badge')?.textContent?.trim()).toBe('1');
    expect(button.getAttribute('aria-label')).toBe('Notifications, 1 unread');
    button.click();
    const seen = http.expectOne(URL + '/seen');
    expect(seen.request.method).toBe('POST');
    seen.flush({ items: [n('a', false), n('b', false, 'transcript')], unread: 0, seen_at: '2026-10-30T09:15:00+00:00' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.bell__badge')).toBeNull();
    const rows = el.querySelectorAll('.bell__item');
    expect(rows.length).toBe(2);
    expect(rows[0].classList.contains('is-new')).toBe(true);        // was unread when opened
    expect(rows[1].classList.contains('is-new')).toBe(false);
    expect(rows[0].textContent).toContain('Title a');
  });

  it('a refresh that was already on its way cannot bring the old unread count back', async () => {
    const { fixture, http, el } = await setup([n('a', true)]);
    (fixture.componentInstance as NotificationBell).load();              // e.g. a navigation refresh, still pending
    const stale = http.expectOne(URL);
    (el.querySelector('.bell__button') as HTMLButtonElement).click();
    http.expectOne(URL + '/seen').flush({ items: [n('a', false)], unread: 0, seen_at: '2026-10-30T09:15:00+00:00' });
    stale.flush({ items: [n('a', true)], unread: 1, seen_at: null });   // arrives last, with the old state
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.bell__badge')).toBeNull();
  });

  it('clears the badge at once and brings it back if saving the read state fails', async () => {
    const { fixture, http, el } = await setup([n('a', true)]);
    (el.querySelector('.bell__button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(el.querySelector('.bell__badge')).toBeNull();                 // before the server answers
    http.expectOne(URL + '/seen').flush({ detail: 'down' }, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.bell__badge')?.textContent?.trim()).toBe('1');
  });

  it('does not call mark-read when nothing is unread, and explains an empty list', async () => {
    const { fixture, http, el } = await setup([]);
    (el.querySelector('.bell__button') as HTMLButtonElement).click();
    http.expectNone(URL + '/seen');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.bell__empty')?.textContent).toContain('No notifications yet');
  });
});
