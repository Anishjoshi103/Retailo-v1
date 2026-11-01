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
});
