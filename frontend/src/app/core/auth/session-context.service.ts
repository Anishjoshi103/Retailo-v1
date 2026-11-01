import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, of, tap } from 'rxjs';
import { APP_CONFIG } from '../config/app-config.token';
import { SessionService } from './session.service';

export interface SessionBranch { readonly id: string; readonly name: string; readonly code: string; }
interface MeResponse {
  readonly id: string; readonly email: string; readonly display_name: string;
  readonly tenant: { readonly id: string; readonly name: string };
  readonly role: string; readonly allowed_branch_ids: readonly string[];
}
@Injectable({ providedIn: 'root' })
export class SessionContextService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(APP_CONFIG);
  private readonly session = inject(SessionService);
  readonly user = signal<MeResponse | null>(null);
  readonly roles = signal<readonly string[]>([]);
  readonly tenantId = signal<string | null>(null);
  readonly branches = signal<readonly SessionBranch[]>([]);
  readonly selectedBranchId = signal<string | null>(null);
  private get base(): string { return this.config.apiBaseUrl.replace(/\/$/, ''); }

  load(): Observable<boolean> {
    return this.http.get<MeResponse>(this.base + '/auth/me').pipe(
      tap((me) => {
        this.user.set(me);
        this.roles.set([me.role]);
        this.tenantId.set(me.tenant.id);
      }),
      map(() => true),
      catchError(() => { this.clear(); return of(false); }),
    );
  }
  loadBranches(): Observable<readonly SessionBranch[]> {
    return this.http.get<SessionBranch[]>(this.base + '/branches').pipe(
      tap((items) => {
        const allowed = this.user()?.allowed_branch_ids ?? [];
        const valid = items.filter((item) => allowed.includes(item.id));
        this.branches.set(valid);
        const current = this.selectedBranchId();
        if (!current || !valid.some((item) => item.id === current)) this.selectedBranchId.set(valid[0]?.id ?? null);
      }),
    );
  }
  selectBranch(id: string): boolean {
    if (!this.branches().some((item) => item.id === id)) return false;
    this.selectedBranchId.set(id);
    return true;
  }
  clear(): void {
    this.user.set(null); this.roles.set([]); this.tenantId.set(null);
    this.branches.set([]); this.selectedBranchId.set(null);
  }
}
