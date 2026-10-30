import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./features/home/home.page').then((module) => module.HomePage)
  },
  { path: '**', redirectTo: '' }
];
