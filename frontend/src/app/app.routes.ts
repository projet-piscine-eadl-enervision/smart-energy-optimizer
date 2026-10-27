import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/auth.guard';
import { Dashboard } from './pages/dashboard/dashboard';
import { Login } from './pages/login/login';
import { Peaks } from './pages/peaks/peaks';
import { Shell } from './shared/shell/shell';

export const routes: Routes = [
  { path: 'login', component: Login, canActivate: [guestGuard] },
  {
    path: '',
    component: Shell,
    canActivate: [authGuard],
    children: [
      { path: '', component: Dashboard },
      { path: 'peaks', component: Peaks },
    ],
  },
  { path: '**', redirectTo: '' },
];
