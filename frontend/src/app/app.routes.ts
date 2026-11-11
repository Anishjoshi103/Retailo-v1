import { Routes } from '@angular/router';
import { authGuard } from './core/auth/auth.guard';
import { roleBranchGuard } from './core/auth/role-branch.guard';

const featurePaths = ['inventory', 'reports', 'settings'];
const allRoles = ['owner', 'admin', 'manager', 'cashier', 'accountant'];
export const routes: Routes = [
  { path: 'auth', loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES) },
  { path: '', canActivate: [authGuard], loadComponent: () => import('./layout/shell/shell.component').then((m) => m.ShellComponent), children: [
    { path: '', pathMatch: 'full', loadComponent: () => import('./features/home/home.page').then((m) => m.HomePage) },
    { path: 'catalog', canActivate: [roleBranchGuard], data: { title: 'Catalog' }, loadComponent: () => import('./features/catalog/catalog.page').then((m) => m.CatalogPage) },
    { path: 'pos', canActivate: [roleBranchGuard], data: { title: 'Point of sale', branchRequired: true, roles: ['owner', 'admin', 'manager', 'cashier'] }, loadComponent: () => import('./features/pos/pos.page').then((m) => m.PosPage) },
    { path: 'gst', canActivate: [roleBranchGuard], data: { title: 'GST & invoices', branchRequired: true, roles: allRoles }, loadComponent: () => import('./features/invoices/invoices.page').then((m) => m.InvoicesPage) },
    { path: 'gst/credit-notes', canActivate: [roleBranchGuard], data: { title: 'Credit notes', branchRequired: true, roles: allRoles }, loadComponent: () => import('./features/returns/credit-notes.page').then((m) => m.CreditNotesPage) },
    { path: 'gst/credit-notes/:id', canActivate: [roleBranchGuard], data: { title: 'Credit note', branchRequired: true, roles: allRoles }, loadComponent: () => import('./features/returns/credit-note-detail.page').then((m) => m.CreditNoteDetailPage) },
    { path: 'gst/:id', canActivate: [roleBranchGuard], data: { title: 'Invoice', branchRequired: true, roles: allRoles }, loadComponent: () => import('./features/invoices/invoice-detail.page').then((m) => m.InvoiceDetailPage) },
    ...featurePaths.map((path) => ({ path, canActivate: [roleBranchGuard], data: { title: featureTitle(path), ...(path === 'reports' ? { roles: ['owner', 'admin', 'manager'] } : {}), ...(path === 'settings' ? { roles: ['owner', 'admin'] } : {}) }, loadComponent: () => import('./features/placeholder/feature-placeholder.page').then((m) => m.FeaturePlaceholderPage) }))
  ] },
  { path: '**', redirectTo: '' }
];
function featureTitle(path: string): string {
  const titles: Readonly<Record<string, string>> = { inventory:'Inventory', pos:'Point of sale', gst:'GST & invoices', reports:'Reports', settings:'Settings' };
  return titles[path] ?? 'Workspace';
}
