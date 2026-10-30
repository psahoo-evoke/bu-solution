import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './api/api.service';
import { AuthService } from './api/auth.service';
import { DemoRole } from './api/models';
import { Operation, can } from './api/permissions';
import { homeHidden, homeRoute } from './api/role-home';
import { RoleService } from './api/role.service';
import { NotificationBell } from './shared/notification-bell';
import { statusTitle } from './shared/status';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NotificationBell],
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);
  protected readonly roleService = inject(RoleService);
  /** null = checking, true = up, false = down */
  protected readonly apiUp = signal<boolean | null>(null);
  /** Developers on localhost get the "start the backend" hint; everyone else gets a plain-language message. */
  protected readonly localDev = ['localhost', '127.0.0.1'].includes(location.hostname);
  protected readonly statusLabel = computed(() => {
    const role = this.roleService.role();
    return role === 'Student' || role === 'Department' ? statusTitle(role) : 'Student status';
  });
  /** Signed-in students and departments have no Home: the link is hidden and the logo opens their own page. */
  protected readonly noHome = computed(() =>
    this.auth.secured() && this.roleService.available().length > 0
      && homeHidden(this.roleService.role(), this.auth.signedIn()),
  );
  protected readonly brandLink = computed(() =>
    this.noHome() ? homeRoute(this.roleService.role(), this.auth.studentId()) : '/',
  );
  /** A signed-in student's link goes straight to their own record. */
  protected readonly studentLink = computed(() => (this.auth.studentId() ? ['/student', this.auth.studentId()!] : ['/student']));

  ngOnInit(): void {
    this.checkHealth();
  }

  checkHealth(): void {
    this.apiUp.set(null);
    this.api.health().subscribe({
      next: () => this.apiUp.set(true),
      error: () => this.apiUp.set(false),
    });
  }

  onRoleChange(value: string): void {
    this.roleService.set(value as DemoRole);
  }

  /** Demo mode shows every page (the role switcher explains what each role can do); signed-in users only see
   * the pages their role can use. */
  protected showNav(op: Operation): boolean {
    return !this.auth.secured() || can(this.roleService.role(), op);
  }

  protected signOut(): void {
    void this.auth.logout().then(() => this.router.navigateByUrl('/'));
  }
}
