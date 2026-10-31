import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthApiError, AuthOptions, AuthService, Portal, PortalUser } from '../api/auth.service';
import { ROLE_LABELS, homeRoute } from '../api/role-home';
import { RoleService } from '../api/role.service';

interface Sample {
  email: string;
  label: string;
}

const SAMPLES: Record<Portal, Sample[]> = {
  // student_loginsample.txt
  student: [
    { email: 'maya.delgado@bu.edu', label: 'Maya R. Delgado · SYN-24001' },
    { email: 'jordan.reyes@bu.edu', label: 'Jordan A. Reyes · SYN-24002' },
    { email: 'aisha.bello@bu.edu', label: 'Aisha K. Bello · SYN-24003' },
    { email: 'liam.novak@bu.edu', label: 'Liam O. Novak · SYN-24004' },
  ],
  department: [
    { email: 'psychology.dept@bu.edu', label: 'Psychology' },
    { email: 'biology.dept@bu.edu', label: 'Biology' },
    { email: 'economics.dept@bu.edu', label: 'Economics' },
    { email: 'computerscience.dept@bu.edu', label: 'Computer Science' },
    { email: 'mathematics.dept@bu.edu', label: 'Mathematics' },
    { email: 'generaleducation.dept@bu.edu', label: 'General education' },
  ],
  staff: [
    { email: 'evaluator@bu.edu', label: 'Evaluator' },
    { email: 'creditstaff@bu.edu', label: 'Credit staff' },
    { email: 'registrar@bu.edu', label: 'Registrar' },
    { email: 'advisor@bu.edu', label: 'Advisor' },
    { email: 'financialaid@bu.edu', label: 'Financial aid' },
  ],
};

const COPY: Record<Portal, { title: string; lead: string; registerLabel: string | null }> = {
  student: {
    title: 'Student sign in',
    lead: 'See your own transfer credit: what is secured, what is pending and what to do next.',
    registerLabel: 'New student? Register',
  },
  department: {
    title: 'Department sign in',
    lead: "Review and decide on your department's transfer courses in the Evaluator workbench.",
    registerLabel: 'New department reviewer? Register',
  },
  staff: {
    title: 'Staff sign in',
    lead: 'Transfer evaluators, credit staff, the Registrar and advisors.',
    registerLabel: null,
  },
};

/** /login/:portal (student | department | staff): portal sign-in and self-registration (portal mode). */
@Component({
  selector: 'app-login',
  imports: [FormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class LoginPage implements OnInit {
  /** Route param, bound by withComponentInputBinding(). */
  readonly portal = input<string>('student');

  protected readonly auth = inject(AuthService);
  private readonly roles = inject(RoleService);
  private readonly router = inject(Router);

  protected readonly kind = computed<Portal>(() => {
    const p = this.portal();
    return p === 'department' || p === 'staff' ? p : 'student';
  });
  protected readonly copy = computed(() => COPY[this.kind()]);
  protected readonly samples = computed(() => SAMPLES[this.kind()]);
  protected readonly labels = ROLE_LABELS;

  protected readonly tab = signal<'signin' | 'register'>('signin');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notRegistered = signal(false);
  protected readonly options = signal<AuthOptions | null>(null);

  // Form fields (template-driven, ngModel).
  email = '';
  password = '';
  confirm = '';
  name = '';
  major = '';
  term = 'Fall 2026';
  department = '';

  ngOnInit(): void {
    this.auth.options().then((o) => this.options.set(o), () => undefined);
  }

  protected show(tab: 'signin' | 'register'): void {
    this.tab.set(tab);
    this.error.set(null);
    this.notRegistered.set(false);
  }

  protected useSample(s: Sample): void {
    this.show('signin');
    this.email = s.email;
    this.password = 'admin';
  }

  protected async signIn(): Promise<void> {
    if (!this.email || !this.password) {
      this.error.set('Enter your email and password.');
      return;
    }
    await this.run(() => this.auth.signIn(this.email, this.password, this.kind()));
  }

  protected async register(): Promise<void> {
    if (this.password !== this.confirm) {
      this.error.set('The two passwords do not match.');
      return;
    }
    const base = { name: this.name, email: this.email, password: this.password };
    await this.run(() =>
      this.kind() === 'department'
        ? this.auth.registerDepartment({ ...base, department: this.department })
        : this.auth.registerStudent({ ...base, intended_major: this.major, start_term: this.term }),
    );
  }

  protected continueAs(): void {
    const role = this.roles.role();
    void this.router.navigateByUrl(homeRoute(role, this.auth.studentId()));
  }

  protected signOut(): void {
    void this.auth.logout();
  }

  private async run(call: () => Promise<PortalUser>): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    this.notRegistered.set(false);
    try {
      const user = await call();
      this.roles.set(user.role);
      await this.router.navigateByUrl(homeRoute(user.role, user.student_id));
    } catch (e) {
      const status = e instanceof AuthApiError ? e.status : 0;
      this.notRegistered.set(status === 404 && this.copy().registerLabel !== null);
      this.error.set(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
    } finally {
      this.busy.set(false);
    }
  }
}
