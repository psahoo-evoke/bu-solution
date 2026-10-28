import { Routes } from '@angular/router';

export const DEFAULT_STUDENT = 'SYN-24001';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: `student/${DEFAULT_STUDENT}` },
  { path: 'student', pathMatch: 'full', redirectTo: `student/${DEFAULT_STUDENT}` },
  {
    path: 'student/:id',
    title: 'Student status · TransferIQ',
    loadComponent: () => import('./pages/student-status').then((m) => m.StudentStatusPage),
  },
  {
    path: 'review',
    title: 'Evaluator workbench · TransferIQ',
    loadComponent: () => import('./pages/review').then((m) => m.ReviewPage),
  },
  {
    path: 'evaluation',
    title: 'AI evaluation · TransferIQ',
    loadComponent: () => import('./pages/evaluation').then((m) => m.EvaluationPage),
  },
  {
    path: 'registrar',
    title: 'Registrar · TransferIQ',
    loadComponent: () => import('./pages/registrar').then((m) => m.RegistrarPage),
  },
  { path: '**', redirectTo: '' },
];
