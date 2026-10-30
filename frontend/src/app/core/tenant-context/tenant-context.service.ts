import { Injectable, signal } from '@angular/core';

export interface TenantContext {
  readonly tenantId: string | null;
  readonly branchId: string | null;
}

@Injectable({ providedIn: 'root' })
export class TenantContextService {
  private readonly contextState = signal<TenantContext>({ tenantId: null, branchId: null });
  readonly context = this.contextState.asReadonly();

  setTenant(tenantId: string | null): void {
    this.contextState.update((current) => ({ ...current, tenantId }));
  }

  setBranch(branchId: string | null): void {
    this.contextState.update((current) => ({ ...current, branchId }));
  }

  clear(): void {
    this.contextState.set({ tenantId: null, branchId: null });
  }
}