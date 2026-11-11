import { describe, expect, it } from 'vitest';
import { authGuard } from './core/auth/auth.guard';
import { roleBranchGuard } from './core/auth/role-branch.guard';
import { routes } from './app.routes';

describe('application routes', () => {
  it('protects the shell, including the home route, with authentication', () => {
    const shell = routes.find((route) => route.path === '');
    expect(shell?.canActivate).toContain(authGuard);
    expect(shell?.children?.find((route) => route.path === '')).toBeDefined();
  });

  it('keeps role-based access checks on restricted feature routes', () => {
    const shell = routes.find((route) => route.path === '');
    const children = shell?.children ?? [];
    expect(children.find((route) => route.path === 'catalog')?.canActivate).toContain(roleBranchGuard);
    expect(children.find((route) => route.path === 'settings')?.canActivate).toContain(roleBranchGuard);
    expect(children.find((route) => route.path === 'reports')?.canActivate).toContain(roleBranchGuard);
  });

  it('serves invoice history and detail at gst for every role, and requires a branch', () => {
    const shell = routes.find((route) => route.path === '');
    for (const path of ['gst', 'gst/:id']) {
      const route = shell?.children?.find((child) => child.path === path);
      expect(route?.canActivate, path).toContain(roleBranchGuard);
      expect(route?.data?.['branchRequired'], path).toBe(true);
      expect(route?.data?.['roles'], path).toEqual(['owner', 'admin', 'manager', 'cashier', 'accountant']);
      expect(route?.loadComponent, path).toBeDefined();
    }
  });

  it('serves credit notes under gst, with the static routes ahead of the invoice id route', () => {
    const shell = routes.find((route) => route.path === '');
    const paths = (shell?.children ?? []).map((route) => route.path);
    expect(paths.indexOf('gst/credit-notes')).toBeGreaterThan(-1);
    expect(paths.indexOf('gst/credit-notes')).toBeLessThan(paths.indexOf('gst/:id'));
    expect(paths.indexOf('gst/credit-notes/:id')).toBeLessThan(paths.indexOf('gst/:id'));
    for (const path of ['gst/credit-notes', 'gst/credit-notes/:id']) {
      const route = shell?.children?.find((child) => child.path === path);
      expect(route?.canActivate, path).toContain(roleBranchGuard);
      expect(route?.data?.['branchRequired'], path).toBe(true);
      expect(route?.data?.['roles'], path).toEqual(['owner', 'admin', 'manager', 'cashier', 'accountant']);
      expect(route?.loadComponent, path).toBeDefined();
    }
  });

  it('serves the billing screen at pos for selling roles only, and requires a branch', () => {
    const shell = routes.find((route) => route.path === '');
    const pos = shell?.children?.find((route) => route.path === 'pos');
    expect(pos?.canActivate).toContain(roleBranchGuard);
    expect(pos?.data?.['branchRequired']).toBe(true);
    expect(pos?.data?.['roles']).toEqual(['owner', 'admin', 'manager', 'cashier']);
    expect(pos?.loadComponent).toBeDefined();
  });
});
