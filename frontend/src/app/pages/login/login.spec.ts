import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../core/auth.service';
import { Login } from './login';

describe('Login', () => {
  let fixture: ComponentFixture<Login>;
  let element: HTMLElement;
  let navigateSpy: ReturnType<typeof vi.spyOn>;
  const authStub = {
    login: vi.fn<(email: string, password: string) => Observable<void>>(),
    register: vi.fn<(email: string, password: string) => Observable<unknown>>(),
  };

  function fillForm(email: string, password: string): void {
    const emailInput = element.querySelector<HTMLInputElement>('input[type=email]')!;
    const passwordInput = element.querySelector<HTMLInputElement>('input[type=password]')!;
    emailInput.value = email;
    emailInput.dispatchEvent(new Event('input'));
    passwordInput.value = password;
    passwordInput.dispatchEvent(new Event('input'));
  }

  async function submitForm(): Promise<void> {
    element.querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    await fixture.whenStable();
  }

  function httpError(status: number): Observable<never> {
    return throwError(() => new HttpErrorResponse({ status }));
  }

  beforeEach(async () => {
    authStub.login.mockReset().mockReturnValue(of(undefined));
    authStub.register.mockReset().mockReturnValue(of({}));

    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), { provide: AuthService, useValue: authStub }],
    }).compileComponents();

    navigateSpy = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture = TestBed.createComponent(Login);
    element = fixture.nativeElement;
    await fixture.whenStable();
  });

  it('affiche le mode connexion par défaut', () => {
    expect(element.querySelector('h1')!.textContent).toContain('Connexion');
  });

  it("n'appelle pas l'API si le formulaire est invalide et affiche les erreurs", async () => {
    fillForm('pas-un-email', 'court');
    await submitForm();

    expect(authStub.login).not.toHaveBeenCalled();
    expect(element.textContent).toContain('Email invalide.');
    expect(element.textContent).toContain('8 caractères minimum.');
  });

  it('connecte puis redirige vers le tableau de bord', async () => {
    fillForm('a@b.fr', 'password123');
    await submitForm();

    expect(authStub.login).toHaveBeenCalledWith('a@b.fr', 'password123');
    expect(navigateSpy).toHaveBeenCalledWith(['/']);
  });

  it('en mode inscription, crée le compte puis se connecte', async () => {
    element.querySelector<HTMLButtonElement>('button[type=button]')!.click();
    await fixture.whenStable();
    expect(element.querySelector('h1')!.textContent).toContain('Créer un compte');

    fillForm('a@b.fr', 'password123');
    await submitForm();

    expect(authStub.register).toHaveBeenCalledWith('a@b.fr', 'password123');
    expect(authStub.login).toHaveBeenCalledWith('a@b.fr', 'password123');
    expect(navigateSpy).toHaveBeenCalledWith(['/']);
  });

  it.each([
    [0, "Impossible de joindre l'API"],
    [401, 'Email ou mot de passe incorrect.'],
    [409, 'Cet email est déjà utilisé.'],
    [422, 'Données invalides'],
    [500, 'Erreur inattendue'],
  ])('affiche un message adapté à une erreur %i', async (status, expectedMessage) => {
    authStub.login.mockReturnValue(httpError(status));
    fillForm('a@b.fr', 'password123');
    await submitForm();

    expect(element.textContent).toContain(expectedMessage);
    expect(navigateSpy).not.toHaveBeenCalled();
    expect(element.querySelector<HTMLButtonElement>('button[type=submit]')!.disabled).toBe(false);
  });
});
