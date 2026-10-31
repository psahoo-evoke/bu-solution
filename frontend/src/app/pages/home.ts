import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../api/auth.service';
import { DemoRole } from '../api/models';
import { ROLE_LABELS, homeRoute } from '../api/role-home';
import { RoleService } from '../api/role.service';

interface ViewCard {
  role: DemoRole;
  title: string;
  lead: string;
  points: string[];
}

/**
 * Home / sign-in page: My view, Student View, Department View (frontpage.txt).
 * Entra mode: each view starts Microsoft single sign-on and opens that view afterwards if the account has the role.
 * Demo mode: each view switches the demo role and opens the view directly.
 */
@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomePage implements OnInit {
  protected readonly auth = inject(AuthService);
  protected readonly roles = inject(RoleService);
  private readonly router = inject(Router);

  protected readonly labels = ROLE_LABELS;
  protected readonly notice = signal<string | null>(null);

  protected readonly views: ViewCard[] = [
    {
      role: 'Student',
      title: 'Student View',
      lead: 'See exactly where your transfer credit stands.',
      points: [
        'Secured vs pending credit at a glance',
        'A plain-language status and next step for every course',
        'Upload your transcript and any missing syllabi',
      ],
    },
    {
      role: 'Department',
      title: 'Department View',
      lead: 'Decide on transfer courses with the evidence in one place.',
      points: [
        'A review queue of courses waiting for your decision',
        'AI comparison with matched topics, gaps and past decisions',
        'Approve one course, or a batch of strong matches',
      ],
    },
  ];

  /** Staff views: one tile per office. Accounts are issued by an administrator, so there is no registration here. */
  protected readonly staffViews: { role: DemoRole; lead: string }[] = [
    { role: 'Advisor', lead: 'See which advisees are waiting on something, and what to tell them.' },
    { role: 'FinancialAid', lead: 'Check whether a student’s transfer units are final or could still change.' },
    { role: 'Evaluator', lead: 'Review transfer courses with the AI comparison and past decisions.' },
    { role: 'CreditStaff', lead: 'Follow the whole process: uploads, review, posting and reminders.' },
    { role: 'Registrar', lead: 'Post approved credit and export it for MyBU.' },
  ];

  /** "My view": who is here and as what. Null when nobody is signed in (portal / entra). */
  protected readonly myView = computed(() => {
    if (this.auth.secured() && !this.auth.signedIn()) return null;
    return {
      name: this.auth.secured() ? this.auth.userName() : null,
      detail: this.auth.studentId() ?? this.auth.department(),
      role: this.roles.role(),
      roles: this.roles.available(),
    };
  });

  protected readonly noRole = computed(() => this.auth.secured() && this.auth.signedIn() && this.roles.available().length === 0);

  ngOnInit(): void {
    // Back from Microsoft sign-in: open the view the user picked, if the account has that role.
    const intent = this.auth.consumeIntent();
    if (intent && this.auth.signedIn()) this.open(intent);
  }

  protected open(role: DemoRole): void {
    this.notice.set(null);
    if (this.auth.secured()) {
      if (!this.auth.signedIn()) {
        if (this.auth.portal()) void this.router.navigateByUrl(`/login/${portalFor(role)}`);
        else void this.auth.login(role);
        return;
      }
      if (!this.roles.available().includes(role)) {
        this.notice.set(
          `You are signed in as ${this.auth.userName()}, which is not a ${ROLE_LABELS[role]} account. ` +
            (this.auth.portal()
              ? `Sign out first, then use the ${ROLE_LABELS[role]} sign-in.`
              : `Ask an administrator to assign the role, or continue with a role you have.`),
        );
        return;
      }
    }
    this.roles.set(role);
    void this.router.navigateByUrl(homeRoute(role, this.auth.studentId()));
  }

  protected buttonLabel(role: DemoRole): string {
    if (!this.auth.secured()) return `Continue as ${ROLE_LABELS[role]}`;
    if (this.auth.signedIn()) return `Open ${ROLE_LABELS[role]} view`;
    return this.auth.portal() ? `${ROLE_LABELS[role]} sign in` : 'Sign in with Microsoft';
  }

  protected signOut(): void {
    void this.auth.logout();
  }
}

function portalFor(role: DemoRole): 'student' | 'department' | 'staff' {
  return role === 'Student' ? 'student' : role === 'Department' ? 'department' : 'staff';
}
