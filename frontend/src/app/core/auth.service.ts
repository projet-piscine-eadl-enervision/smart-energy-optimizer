import { HttpClient, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, PLATFORM_ID, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { map, Observable, tap } from 'rxjs';
import { API_URL } from './api.config';
import { Token, User } from './models';

const TOKEN_KEY = 'enervision_token';

/**
 * Inscription, connexion, déconnexion.
 * Le jeton JWT est gardé dans le localStorage pour survivre au rechargement de la page.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  // Avec le SSR, ce code peut tourner sur le serveur Node, où localStorage n'existe pas
  private readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  private readonly tokenSignal = signal<string | null>(this.readToken());
  readonly isLoggedIn = computed(() => this.tokenSignal() !== null);

  /** Compte connecté, chargé par loadUser() ; vide tant qu'il n'est pas connu. */
  readonly user = signal<User | null>(null);
  readonly isAdmin = computed(() => this.user()?.role === 'admin');
  /** Un `user` sans site attribué : l'API lui refuse toutes les données (403). */
  readonly hasNoSite = computed(() => {
    const u = this.user();
    return u !== null && u.role !== 'admin' && !u.site_id;
  });

  token(): string | null {
    return this.tokenSignal();
  }

  register(email: string, password: string): Observable<User> {
    return this.http.post<User>(`${API_URL}/auth/register`, { email, password });
  }

  login(email: string, password: string): Observable<void> {
    // /login attend un formulaire (OAuth2PasswordRequestForm), pas du JSON
    const body = new HttpParams().set('username', email).set('password', password);
    return this.http.post<Token>(`${API_URL}/auth/login`, body).pipe(
      tap((res) => this.saveToken(res.access_token)),
      map(() => undefined)
    );
  }

  me(): Observable<User> {
    return this.http.get<User>(`${API_URL}/auth/me`);
  }

  /** Charge le compte connecté et le garde dans `user`. */
  loadUser(): Observable<User> {
    return this.me().pipe(tap((u) => this.user.set(u)));
  }

  logout(): void {
    this.user.set(null);
    this.saveToken(null);
    this.router.navigate(['/login']);
  }

  private readToken(): string | null {
    return this.isBrowser ? localStorage.getItem(TOKEN_KEY) : null;
  }

  private saveToken(token: string | null): void {
    if (this.isBrowser) {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    }
    this.tokenSignal.set(token);
  }
}
