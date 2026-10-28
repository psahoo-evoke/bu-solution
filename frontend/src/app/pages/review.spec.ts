import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { roleInterceptor } from '../api/role.interceptor';
import { RoleService } from '../api/role.service';
import { ReviewPage } from './review';

describe('ReviewPage role gating', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [ReviewPage],
      providers: [provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('does not request review data as Student and explains which role to use', async () => {
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    http.expectNone((r) => r.url === '/api/review-queue');
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Switch role to CreditStaff, Evaluator or Department to open the review queue.');
    expect((fixture.nativeElement as HTMLElement).querySelector('.workbench')).toBeNull();
  });

  it('loads reason codes from the API and the queue as Evaluator', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    const codes = http.expectOne('/api/reason-codes');
    expect(codes.request.headers.get('X-Demo-Role')).toBe('Evaluator');
    codes.flush([
      { reason_code: 'EQ-CONTENT', decision: 'Equivalent', meaning: 'Substantially equivalent' },
      { reason_code: 'NC-GRADE', decision: 'No credit', meaning: 'Grade below C' },
    ]);
    http.expectOne((r) => r.url === '/api/review-queue').flush([]);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('.workbench')).not.toBeNull();
  });
});
