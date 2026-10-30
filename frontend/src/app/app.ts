import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './api/api.service';
import { AuthService } from './api/auth.service';
import { DemoRole } from './api/models';
import { Operation, can } from './api/permissions';
import { RoleService } from './api/role.service';
import { NotificationBell } from './shared/notification-bell';

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
