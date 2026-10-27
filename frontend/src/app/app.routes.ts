import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/auth.guard';
import { Dashboard } from './pages/dashboard/dashboard';
import { Login } from './pages/login/login';
import { Alerts } from './pages/alerts/alerts';
import { Peaks } from './pages/peaks/peaks';
import { SiteDetail } from './pages/site-detail/site-detail';
import { Sites } from './pages/sites/sites';
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
      { path: 'alerts', component: Alerts },
      { path: 'sites', component: Sites },
      { path: 'sites/:id', component: SiteDetail },
    ],
  },
  { path: '**', redirectTo: '' },
];
