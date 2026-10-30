import { Routes } from '@angular/router';
import { authGuard } from './api/auth.guard';

export const DEFAULT_STUDENT = 'SYN-24001';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'TransferIQ · Transfer credit co-pilot',
    loadComponent: () => import('./pages/home').then((m) => m.HomePage),
  },
  {
    path: 'login/:portal',
    title: 'Sign in · TransferIQ',
    loadComponent: () => import('./pages/login').then((m) => m.LoginPage),
  },
  {
    path: 'credit-check',
    title: 'Will my course transfer? · TransferIQ',
    loadComponent: () => import('./pages/credit-check').then((m) => m.CreditCheckPage),   // public, no sign-in
  },
  { path: 'student', pathMatch: 'full', redirectTo: `student/${DEFAULT_STUDENT}` },
  {
    path: 'student/:id',
    title: 'Student status · TransferIQ',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/student-status').then((m) => m.StudentStatusPage),
  },
  {
    path: 'review',
    title: 'Evaluator workbench · TransferIQ',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/review').then((m) => m.ReviewPage),
  },
  {
    path: 'evaluation',
    title: 'AI evaluation · TransferIQ',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/evaluation').then((m) => m.EvaluationPage),
  },
  {
    path: 'registrar',
    title: 'Registrar · TransferIQ',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/registrar').then((m) => m.RegistrarPage),
  },
  { path: '**', redirectTo: '' },
];
