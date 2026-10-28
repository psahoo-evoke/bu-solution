import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { roleInterceptor } from './api/role.interceptor';
import { App } from './app';

describe('App shell', () => {
  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('shows the synthetic-data badge and the role switcher', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/health').flush({ status: 'ok' });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Synthetic data – EvoHack 2026');
    const options = Array.from(el.querySelectorAll('#role-select option')).map((o) => o.textContent?.trim());
    expect(options).toEqual(['Student', 'CreditStaff', 'Evaluator', 'Department', 'Registrar', 'Advisor']);
  });

  it('shows an error banner (not a blank page) when the API is down', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/health')
      .error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();
    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('API offline');
  });
});
