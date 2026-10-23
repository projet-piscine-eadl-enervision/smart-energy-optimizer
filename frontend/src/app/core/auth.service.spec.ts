import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { Token, User } from './models';

const TOKEN_KEY = 'enervision_token';

describe('AuthService', () => {
  let httpMock: HttpTestingController;

  function createService(): AuthService {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    httpMock = TestBed.inject(HttpTestingController);
    return TestBed.inject(AuthService);
  }

  beforeEach(() => localStorage.clear());
  afterEach(() => httpMock.verify());

  it("n'est pas connecté sans jeton enregistré", () => {
    const service = createService();
    expect(service.isLoggedIn()).toBe(false);
    expect(service.token()).toBeNull();
  });

  it('reprend le jeton du localStorage au démarrage', () => {
    localStorage.setItem(TOKEN_KEY, 'saved-token');
    const service = createService();
    expect(service.isLoggedIn()).toBe(true);
    expect(service.token()).toBe('saved-token');
  });

  it('login envoie un formulaire et enregistre le jeton reçu', () => {
    const service = createService();
    let completed = false;
    service.login('a@b.fr', 'password123').subscribe(() => (completed = true));

    const req = httpMock.expectOne('/api/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.toString()).toBe('username=a@b.fr&password=password123');
    req.flush({ access_token: 'new-token', token_type: 'bearer' } satisfies Token);

    expect(completed).toBe(true);
    expect(service.token()).toBe('new-token');
    expect(service.isLoggedIn()).toBe(true);
    expect(localStorage.getItem(TOKEN_KEY)).toBe('new-token');
  });

  it("login en échec n'enregistre pas de jeton", () => {
    const service = createService();
    let failed = false;
    service.login('a@b.fr', 'bad').subscribe({ error: () => (failed = true) });

    httpMock.expectOne('/api/auth/login').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(failed).toBe(true);
    expect(service.isLoggedIn()).toBe(false);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('register envoie email et mot de passe en JSON', () => {
    const service = createService();
    const user: User = {
      id: 1,
      email: 'a@b.fr',
      is_active: true,
      role: 'user',
      created_at: '2026-10-23T00:00:00Z',
    };
    let received: User | undefined;
    service.register('a@b.fr', 'password123').subscribe((u) => (received = u));

    const req = httpMock.expectOne('/api/auth/register');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'a@b.fr', password: 'password123' });
    req.flush(user);

    expect(received).toEqual(user);
  });

  it('me interroge /api/auth/me', () => {
    const service = createService();
    service.me().subscribe();
    const req = httpMock.expectOne('/api/auth/me');
    expect(req.request.method).toBe('GET');
    req.flush({});
  });

  it('logout efface le jeton et renvoie vers /login', () => {
    localStorage.setItem(TOKEN_KEY, 'saved-token');
    const service = createService();
    const navigateSpy = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    service.logout();

    expect(service.isLoggedIn()).toBe(false);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(navigateSpy).toHaveBeenCalledWith(['/login']);
  });
});
