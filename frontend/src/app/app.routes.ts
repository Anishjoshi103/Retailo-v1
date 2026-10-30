import { Routes } from '@angular/router';
import { authGuard } from './core/auth/auth.guard';
import { roleBranchGuard } from './core/auth/role-branch.guard';
const featurePaths = ['catalog', 'inventory', 'pos', 'gst', 'reports', 'settings'];
export const routes: Routes = [
  { path: '', loadComponent: () => import('./layout/shell/shell.component').then((m) => m.ShellComponent), children: [
    { path: '', pathMatch: 'full', loadComponent: () => import('./features/home/home.page').then((m) => m.HomePage) },
    { path: 'auth', loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES) },
    ...featurePaths.map((path) => ({ path, canActivate: [authGuard, roleBranchGuard], data: { title: featureTitle(path) }, loadComponent: () => import('./features/placeholder/feature-placeholder.page').then((m) => m.FeaturePlaceholderPage) }))
  ] },
  { path: '**', redirectTo: '' }
];
function featureTitle(path: string): string {
  const titles: Readonly<Record<string, string>> = { catalog:'Catalog', inventory:'Inventory', pos:'Point of sale', gst:'GST & invoices', reports:'Reports', settings:'Settings' };
  return titles[path] ?? 'Workspace';
}