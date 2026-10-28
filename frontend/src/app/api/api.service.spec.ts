import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiService } from './api.service';
import { roleInterceptor } from './role.interceptor';
import { RoleService } from './role.service';

describe('ApiService + roleInterceptor', () => {
  let api: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    });
    api = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('URL-encodes ext_id ("SCHOOL|CODE") in the recommendation path', () => {
    api.getRecommendation('NYU|PSYCH-UA 10').subscribe();
    const req = http.expectOne('/api/courses/NYU%7CPSYCH-UA%2010/recommendation');
    expect(req.request.method).toBe('GET');
    req.flush({});
  });

  it('adds X-Demo-Role from the role switcher', () => {
    TestBed.inject(RoleService).set('Evaluator');
    api.getReviewQueue('Psychology').subscribe();
    const req = http.expectOne((r) => r.url === '/api/review-queue');
    expect(req.request.headers.get('X-Demo-Role')).toBe('Evaluator');
    expect(req.request.params.get('department')).toBe('Psychology');
    req.flush([]);
  });

  it('loads reason codes from GET /api/reason-codes', () => {
    api.listReasonCodes().subscribe((codes) => expect(codes[0].reason_code).toBe('EQ-CONTENT'));
    http.expectOne('/api/reason-codes').flush([{ reason_code: 'EQ-CONTENT', decision: 'Equivalent', meaning: 'x' }]);
  });

  it('sends the default Student role on first load', () => {
    api.getStudentEvaluation('SYN-24001').subscribe();
    const req = http.expectOne('/api/students/SYN-24001/evaluation');
    expect(req.request.headers.get('X-Demo-Role')).toBe('Student');
    req.flush({});
  });

  it('posts a batch with ext_ids and evaluator', () => {
    api.postBatch({ ext_ids: ['NEU|CS 1800'], evaluator: 'Demo Evaluator' }).subscribe();
    const req = http.expectOne('/api/decisions/batch');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ ext_ids: ['NEU|CS 1800'], evaluator: 'Demo Evaluator' });
    req.flush([]);
  });
});
