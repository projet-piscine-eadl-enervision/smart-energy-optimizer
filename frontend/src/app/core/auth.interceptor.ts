import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { API_URL } from './api.config';
import { AuthService } from './auth.service';

/**
 * Passe sur chaque requête HTTP avant son envoi :
 * - ajoute « Authorization: Bearer <jeton> » si on est connecté ;
 * - si l'API répond 401 (jeton expiré ou invalide), déconnecte et renvoie vers /login.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // On n'envoie jamais le jeton à un autre site que notre API
  if (!req.url.startsWith(API_URL)) {
    return next(req);
  }

  const auth = inject(AuthService);
  const token = auth.token();
  const authReq = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(authReq).pipe(
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && err.status === 401 && token) {
        auth.logout();
      }
      return throwError(() => err);
    }),
  );
};
