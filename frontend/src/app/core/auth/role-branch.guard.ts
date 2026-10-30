import { inject, Injectable, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
export interface RouteAccessData { readonly roles?: readonly string[]; readonly branchRequired?: boolean; }
@Injectable({ providedIn: 'root' })
export class RouteRoleContext { readonly roles = signal<readonly string[]>([]); readonly branchId = signal<string | null>(null); }
export const roleBranchGuard: CanActivateFn = (route) => {
  const data = route.data as RouteAccessData; const context = inject(RouteRoleContext);
  if (data.roles?.length && !data.roles.some((role) => context.roles().includes(role))) return inject(Router).createUrlTree(['/']);
  if (data.branchRequired && !context.branchId()) return inject(Router).createUrlTree(['/']);
  return true;
};