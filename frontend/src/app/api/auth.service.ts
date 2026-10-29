import { Injectable, computed, signal } from '@angular/core';
import type { AccountInfo, IPublicClientApplication } from '@azure/msal-browser';
import { DEMO_ROLES, DemoRole } from './models';

/** /auth-config.json: rendered by nginx from env in the container, public/auth-config.json (demo) in dev. */
export interface AuthConfig {
  mode: 'demo' | 'entra';
  clientId?: string;
  tenantId?: string;
  /** Scope for API tokens; default `<clientId>/.default` (the SPA and API share one app registration). */
  apiScope?: string;
}

/**
 * Entra ID sign-in (TRANSFERIQ_AUTH_MODE=entra on the API). In demo mode nothing is loaded and the role
 * comes from the top-bar switcher. In entra mode the user's roles are the `roles` claim (Entra app roles) and
 * every /api call carries an access token; the API re-validates the token and the roles (backend/app/guard.py).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly config = signal<AuthConfig>({ mode: 'demo' });
  readonly account = signal<AccountInfo | null>(null);
  readonly error = signal<string | null>(null);
  readonly entra = computed(() => this.config().mode === 'entra');
  readonly signedIn = computed(() => this.account() !== null);
  readonly userName = computed(() => this.account()?.name || this.account()?.username || '');
  /** Roles from the ID token, in DEMO_ROLES order (unknown role names are ignored). */
  readonly roles = computed<DemoRole[]>(() => {
    const claimed = (this.account()?.idTokenClaims as { roles?: string[] } | undefined)?.roles ?? [];
    return DEMO_ROLES.filter((r) => claimed.includes(r));
  });

  private msal: IPublicClientApplication | null = null;

  /** Runs before the first route (provideAppInitializer); completes a sign-in redirect if one is in progress. */
  async init(): Promise<void> {
    let cfg: AuthConfig = { mode: 'demo' };
    try {
      const res = await fetch('/auth-config.json', { cache: 'no-store' });
      if (res.ok) cfg = (await res.json()) as AuthConfig;
    } catch {
      /* no config file: demo mode */
    }
    if (cfg.mode !== 'entra') return;
    this.config.set(cfg);
    if (!cfg.clientId || !cfg.tenantId) {
      this.error.set('Sign-in is not configured (missing Entra client or tenant id).');
      return;
    }
    try {
      // Loaded only in entra mode, so the demo bundle stays small.
      const { createStandardPublicClientApplication } = await import('@azure/msal-browser');
      this.msal = await createStandardPublicClientApplication({
        auth: {
          clientId: cfg.clientId,
          authority: `https://login.microsoftonline.com/${cfg.tenantId}`,
          redirectUri: window.location.origin,
        },
        cache: { cacheLocation: 'sessionStorage' },
      });
      const result = await this.msal.handleRedirectPromise();
      const account = result?.account ?? this.msal.getActiveAccount() ?? this.msal.getAllAccounts()[0] ?? null;
      if (account) this.msal.setActiveAccount(account);
      this.account.set(account);
    } catch (e) {
      this.error.set(`Sign-in failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  login(): Promise<void> {
    return this.msal ? this.msal.loginRedirect({ scopes: [this.scope()] }) : Promise.resolve();
  }

  logout(): Promise<void> {
    return this.msal ? this.msal.logoutRedirect({ account: this.account() ?? undefined }) : Promise.resolve();
  }

  /** Access token for the API (null in demo mode). Redirects to sign-in when Entra needs interaction. */
  async accessToken(): Promise<string | null> {
    const account = this.account();
    if (!this.entra() || !this.msal || !account) return null;
    try {
      return (await this.msal.acquireTokenSilent({ scopes: [this.scope()], account })).accessToken;
    } catch (e) {
      const { InteractionRequiredAuthError } = await import('@azure/msal-browser');
      if (e instanceof InteractionRequiredAuthError) {
        await this.msal.acquireTokenRedirect({ scopes: [this.scope()], account });
      }
      throw e;
    }
  }

  private scope(): string {
    const cfg = this.config();
    return cfg.apiScope || `${cfg.clientId}/.default`;
  }
}
