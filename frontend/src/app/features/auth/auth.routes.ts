import { Routes } from '@angular/router';
export const AUTH_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: 'login', loadComponent: () => import('./login.page').then((m) => m.LoginPage) },
  { path: 'register', loadComponent: () => import('./register.page').then((m) => m.RegisterPage) },
  { path: 'verify-email', loadComponent: () => import('./verify-email.page').then((m) => m.VerifyEmailPage) },
  { path: 'password-reset/confirm', loadComponent: () => import('./password-reset-confirm.page').then((m) => m.PasswordResetConfirmPage) },
  { path: 'password-recovery', loadComponent: () => import('./password-recovery.page').then((m) => m.PasswordRecoveryPage) }
];
