import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let currentToken: string | null;
  const logout = vi.fn();

  beforeEach(() => {
    currentToken = null;
    logout.mockReset();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { token: () => currentToken, logout } },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it("ajoute le jeton aux requêtes vers l'API", () => {
    currentToken = 'abc';
    http.get('/api/predictions').subscribe();
    const req = httpMock.expectOne('/api/predictions');
    expect(req.request.headers.get('Authorization')).toBe('Bearer abc');
    req.flush([]);
  });

  it("n'ajoute rien sans jeton", () => {
    http.get('/api/predictions').subscribe();
    const req = httpMock.expectOne('/api/predictions');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush([]);
  });

  it("n'envoie jamais le jeton à un autre site", () => {
    currentToken = 'abc';
    http.get('https://example.com/data').subscribe();
    const req = httpMock.expectOne('https://example.com/data');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('déconnecte sur une réponse 401 et propage l’erreur', () => {
    currentToken = 'expired';
    let status: number | undefined;
    http.get('/api/auth/me').subscribe({ error: (err) => (status = err.status) });

    httpMock.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(logout).toHaveBeenCalledOnce();
    expect(status).toBe(401);
  });

  it('ne déconnecte pas sur un 401 sans jeton (mauvais identifiants)', () => {
    http.post('/api/auth/login', {}).subscribe({ error: () => undefined });
    httpMock.expectOne('/api/auth/login').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(logout).not.toHaveBeenCalled();
  });

  it('ne déconnecte pas sur une autre erreur', () => {
    currentToken = 'abc';
    http.get('/api/predictions').subscribe({ error: () => undefined });
    httpMock.expectOne('/api/predictions').flush(null, { status: 500, statusText: 'Server Error' });
    expect(logout).not.toHaveBeenCalled();
  });
});
