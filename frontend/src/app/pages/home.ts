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

  protected readonly staff: { role: DemoRole; what: string }[] = [
    { role: 'Evaluator', what: 'Review and decide' },
    { role: 'CreditStaff', what: 'Triage and uploads' },
    { role: 'Registrar', what: 'Post credit and export' },
    { role: 'Advisor', what: 'Read-only student view' },
  ];

  /** "My view": who is here and as what. Null when nobody is signed in (entra) */
  protected readonly myView = computed(() => {
    if (this.auth.entra() && !this.auth.signedIn()) return null;
    return {
      name: this.auth.entra() ? this.auth.userName() : null,
      role: this.roles.role(),
      roles: this.roles.available(),
    };
  });

  protected readonly noRole = computed(() => this.auth.entra() && this.auth.signedIn() && this.roles.available().length === 0);

  ngOnInit(): void {
    // Back from Microsoft sign-in: open the view the user picked, if the account has that role.
    const intent = this.auth.consumeIntent();
    if (intent && this.auth.signedIn()) this.open(intent);
  }

  protected open(role: DemoRole): void {
    this.notice.set(null);
    if (this.auth.entra()) {
      if (!this.auth.signedIn()) {
        void this.auth.login(role);
        return;
      }
      if (!this.roles.available().includes(role)) {
        this.notice.set(
          `Your account is not assigned the ${ROLE_LABELS[role]} role. ` +
            `Ask an administrator to assign it, or continue with a role you have.`,
        );
        return;
      }
    }
    this.roles.set(role);
    void this.router.navigateByUrl(homeRoute(role));
  }

  protected buttonLabel(role: DemoRole): string {
    if (!this.auth.entra()) return `Continue as ${ROLE_LABELS[role]}`;
    return this.auth.signedIn() ? `Open ${ROLE_LABELS[role]} view` : 'Sign in with Microsoft';
  }
}
