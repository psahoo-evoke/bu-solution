import { Routes } from '@angular/router';
import { authGuard, pageGuard } from './api/auth.guard';
import { DEFAULT_STUDENT } from './api/defaults';

export { DEFAULT_STUDENT };

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
    canActivate: [authGuard, pageGuard('review')],
    loadComponent: () => import('./pages/review').then((m) => m.ReviewPage),
  },
  {
    path: 'evaluation',
    title: 'AI evaluation · TransferIQ',
    canActivate: [authGuard, pageGuard('evaluation')],
    loadComponent: () => import('./pages/evaluation').then((m) => m.EvaluationPage),
  },
  {
    path: 'registrar',
    title: 'Registrar · TransferIQ',
    canActivate: [authGuard, pageGuard('registrar')],
    loadComponent: () => import('./pages/registrar').then((m) => m.RegistrarPage),
  },
  {
    path: 'advisor',
    title: 'Advisor caseload · TransferIQ',
    canActivate: [authGuard, pageGuard('advisor')],
    loadComponent: () => import('./pages/advisor').then((m) => m.AdvisorPage),
  },
  {
    path: 'financial-aid',
    title: 'Financial aid · TransferIQ',
    canActivate: [authGuard, pageGuard('financialAid')],
    loadComponent: () => import('./pages/financial-aid').then((m) => m.FinancialAidPage),
  },
  { path: '**', redirectTo: '' },
];
