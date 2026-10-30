import { Routes } from '@angular/router';
export const AUTH_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: 'login', loadComponent: () => import('./login.page').then((m) => m.LoginPage) }
];
