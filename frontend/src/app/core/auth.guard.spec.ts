import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  CanActivateFn,
  provideRouter,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { authGuard, guestGuard } from './auth.guard';
import { AuthService } from './auth.service';

describe('auth guards', () => {
  const loggedIn = signal(false);

  function runGuard(guard: CanActivateFn): ReturnType<CanActivateFn> {
    return TestBed.runInInjectionContext(() =>
      guard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
    );
  }

  function urlOf(result: ReturnType<CanActivateFn>): string {
    expect(result).toBeInstanceOf(UrlTree);
    return (result as UrlTree).toString();
  }

  beforeEach(() => {
    loggedIn.set(false);
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { isLoggedIn: loggedIn } }],
    });
  });

  describe('authGuard', () => {
    it('laisse passer un utilisateur connecté', () => {
      loggedIn.set(true);
      expect(runGuard(authGuard)).toBe(true);
    });

    it('renvoie un visiteur vers /login', () => {
      expect(urlOf(runGuard(authGuard))).toBe('/login');
    });
  });

  describe('guestGuard', () => {
    it('laisse un visiteur accéder à la connexion', () => {
      expect(runGuard(guestGuard)).toBe(true);
    });

    it('renvoie un utilisateur connecté vers le tableau de bord', () => {
      loggedIn.set(true);
      expect(urlOf(runGuard(guestGuard))).toBe('/');
    });
  });
});
