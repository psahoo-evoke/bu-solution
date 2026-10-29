import { Injectable, computed, signal } from '@angular/core';
import type { AccountInfo, IPublicClientApplication } from '@azure/msal-browser';
import { DEMO_ROLES, DemoRole } from './models';

const INTENT_KEY = 'transferiq.loginIntent';
const SESSION_KEY = 'transferiq.portalSession';

export type AuthMode = 'demo' | 'entra' | 'portal';
export type Portal = 'student' | 'department' | 'staff';

/** /auth-config.json: rendered by nginx from env in the container, public/auth-config.json (demo) in dev. */
export interface AuthConfig {
  mode: AuthMode;
  clientId?: string;
  tenantId?: string;
  /** Scope for API tokens; default `<clientId>/.default` (the SPA and API share one app registration). */
  apiScope?: string;
}

/** Portal account (TRANSFERIQ_AUTH_MODE=portal, backend/app/accounts.py). */
export interface PortalUser {
  email: string;
  name: string;
  role: DemoRole;
  student_id: string | null;
  department: string | null;
}

export interface PortalSession {
  token: string;
  user: PortalUser;
  expires_in: number;
}

export interface AuthOptions {
  mode: string;
  departments: string[];
  majors: string[];
  terms: string[];
}

/** Error from /api/auth with the HTTP status (404 = no account, 401 = wrong password, 409 = already registered). */
export class AuthApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * Who is signed in and how. Three modes (from /auth-config.json):
 * - demo: no sign-in; the role comes from the top-bar switcher.
 * - portal: TransferIQ accounts (student / department / staff) with a session token from /api/auth/login.
 * - entra: Microsoft Entra ID single sign-on; roles are the token's app roles.
 * In portal and entra mode every /api call carries a bearer token and the API re-checks the user and role
 * (backend/app/guard.py).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly config = signal<AuthConfig>({ mode: 'demo' });
  readonly account = signal<AccountInfo | null>(null);
  readonly portalUser = signal<PortalUser | null>(null);
  readonly error = signal<string | null>(null);
  /** One-off message for the home page, e.g. "your session has expired". */
  readonly notice = signal<string | null>(null);
  /** The view the user chose on the home page before the sign-in redirect (Student View, Department View). */
  readonly intent = signal<DemoRole | null>(null);

  readonly entra = computed(() => this.config().mode === 'entra');
  readonly portal = computed(() => this.config().mode === 'portal');
  /** Sign-in required (portal or entra). */
  readonly secured = computed(() => this.config().mode !== 'demo');
  readonly signedIn = computed(() => this.account() !== null || this.portalUser() !== null);
  readonly userName = computed(
    () => this.portalUser()?.name || this.account()?.name || this.account()?.username || '',
  );
  readonly email = computed(() => this.portalUser()?.email || this.account()?.username || '');
  readonly studentId = computed(() => this.portalUser()?.student_id ?? null);
  readonly department = computed(() => this.portalUser()?.department ?? null);
  /** Roles of the signed-in user in DEMO_ROLES order (portal: the account's role; entra: the token's app roles). */
  readonly roles = computed<DemoRole[]>(() => {
    const portalRole = this.portalUser()?.role;
    const claimed = portalRole
      ? [portalRole]
      : ((this.account()?.idTokenClaims as { roles?: string[] } | undefined)?.roles ?? []);
    return DEMO_ROLES.filter((r) => claimed.includes(r));
  });

  private msal: IPublicClientApplication | null = null;
  private token: string | null = null;

  /** Runs before the first route (provideAppInitializer). */
  async init(): Promise<void> {
    let cfg: AuthConfig = { mode: 'demo' };
    try {
      const res = await fetch('/auth-config.json', { cache: 'no-store' });
      if (res.ok) cfg = (await res.json()) as AuthConfig;
    } catch {
      /* no config file: demo mode */
    }
    if (cfg.mode === 'portal') {
      this.config.set(cfg);
      this.restorePortalSession();
      return;
    }
    if (cfg.mode !== 'entra') return;
    this.config.set(cfg);
    if (!cfg.clientId || !cfg.tenantId) {
      this.error.set('Sign-in is not configured (missing Entra client or tenant id).');
      return;
    }
    try {
      // Loaded only in entra mode, so the other modes' bundle stays small.
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
      if (result) this.intent.set(AuthService.takeIntent());
    } catch (e) {
      this.error.set(`Sign-in failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  // ------------------------------------------------------------------ portal accounts
  signIn(email: string, password: string, portal: Portal): Promise<PortalUser> {
    return this.portalCall('/api/auth/login', { email, password, portal });
  }

  registerStudent(body: { name: string; email: string; password: string; intended_major: string; start_term: string }) {
    return this.portalCall('/api/auth/register/student', body);
  }

  registerDepartment(body: { name: string; email: string; password: string; department: string }) {
    return this.portalCall('/api/auth/register/department', body);
  }

  async options(): Promise<AuthOptions> {
    const res = await fetch('/api/auth/options', { cache: 'no-store' });
    if (!res.ok) throw new AuthApiError(res.status, 'Could not load the sign-up options');
    return (await res.json()) as AuthOptions;
  }

  /**
   * The API answered 401. Signed in (portal): the session is gone server-side (expired, or the API restarted),
   * so sign out locally and explain. Demo mode: the site was switched to sign-in after this tab loaded, so
   * reload to pick up the current /auth-config.json. Returns true when a reload was started.
   */
  async handleUnauthorized(): Promise<boolean> {
    if (this.portal()) {
      if (this.portalUser()) this.notice.set('Your session has expired. Please sign in again.');
      this.endPortalSession();
      return false;
    }
    if (this.secured()) return false;
    try {
      const res = await fetch('/auth-config.json', { cache: 'no-store' });
      const cfg = res.ok ? ((await res.json()) as AuthConfig) : null;
      if (cfg && cfg.mode !== 'demo') {
        window.location.reload();
        return true;
      }
    } catch {
      /* keep the current page */
    }
    return false;
  }

  /** Drop the portal session (sign-out, or the API said it expired). */
  endPortalSession(): void {
    this.token = null;
    this.portalUser.set(null);
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }

  private async portalCall(url: string, body: unknown): Promise<PortalUser> {
    let res: Response;
    try {
      res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch {
      throw new AuthApiError(0, 'The TransferIQ API is not reachable. Try again in a moment.');
    }
    const data = (await res.json().catch(() => ({}))) as Partial<PortalSession> & { detail?: unknown };
    if (!res.ok || !data.token || !data.user) {
      throw new AuthApiError(res.status, AuthService.detailText(data.detail) || `Sign-in failed (${res.status})`);
    }
    this.token = data.token;
    this.portalUser.set(data.user);
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ token: data.token, user: data.user }));
    } catch {
      /* storage blocked: the session lasts until the tab reloads */
    }
    return data.user;
  }

  private restorePortalSession(): void {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return;
      const { token, user } = JSON.parse(raw) as { token: string; user: PortalUser };
      if (AuthService.expired(token)) {
        sessionStorage.removeItem(SESSION_KEY);
        return;
      }
      this.token = token;
      this.portalUser.set(user);
    } catch {
      /* corrupt or blocked storage: signed out */
    }
  }

  private static expired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) as { exp?: number };
      return !payload.exp || payload.exp * 1000 <= Date.now();
    } catch {
      return true;
    }
  }

  private static detailText(detail: unknown): string {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : '')).filter(Boolean).join('; ');
    }
    return '';
  }

  // ------------------------------------------------------------------ Microsoft Entra ID
  /** Microsoft sign-in (redirect). `intent` = the view to open afterwards; it survives the redirect. */
  login(intent?: DemoRole): Promise<void> {
    if (!this.msal) return Promise.resolve();
    try {
      if (intent) sessionStorage.setItem(INTENT_KEY, intent);
      else sessionStorage.removeItem(INTENT_KEY);
    } catch {
      /* storage blocked: the user just lands on the home page */
    }
    return this.msal.loginRedirect({ scopes: [this.scope()], prompt: 'select_account' });
  }

  /** Returns and clears the view chosen before sign-in. */
  consumeIntent(): DemoRole | null {
    const intent = this.intent();
    this.intent.set(null);
    return intent;
  }

  private static takeIntent(): DemoRole | null {
    try {
      const value = sessionStorage.getItem(INTENT_KEY) as DemoRole | null;
      sessionStorage.removeItem(INTENT_KEY);
      return value && DEMO_ROLES.includes(value) ? value : null;
    } catch {
      return null;
    }
  }

  logout(): Promise<void> {
    if (this.portal()) {
      this.endPortalSession();
      return Promise.resolve();
    }
    return this.msal ? this.msal.logoutRedirect({ account: this.account() ?? undefined }) : Promise.resolve();
  }

  /** Bearer token for the API (null in demo mode or when signed out). */
  async accessToken(): Promise<string | null> {
    if (this.portal()) {
      if (this.token && AuthService.expired(this.token)) this.endPortalSession();
      return this.token;
    }
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
