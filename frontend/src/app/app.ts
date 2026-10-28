import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './api/api.service';
import { DEMO_ROLES, DemoRole } from './api/models';
import { RoleService } from './api/role.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly roles = DEMO_ROLES;
  protected readonly roleService = inject(RoleService);
  /** null = checking, true = up, false = down */
  protected readonly apiUp = signal<boolean | null>(null);

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
}
