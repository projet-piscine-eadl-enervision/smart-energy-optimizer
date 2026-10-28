import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { switchMap } from 'rxjs';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly mode = signal<'login' | 'register'>('login');
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  protected toggleMode(): void {
    this.mode.update((m) => (m === 'login' ? 'register' : 'login'));
    this.error.set(null);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { email, password } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set(null);

    // Inscription = créer le compte puis se connecter directement
    const request =
      this.mode() === 'login'
        ? this.auth.login(email, password)
        : this.auth.register(email, password).pipe(switchMap(() => this.auth.login(email, password)));

    request.subscribe({
      next: () => this.router.navigate(['/']),
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(errorMessage(err));
      },
    });
  }
}

function errorMessage(err: HttpErrorResponse): string {
  switch (err.status) {
    case 0:
      return "Impossible de joindre l'API. Est-elle démarrée (docker compose up) ?";
    case 401:
      return 'Email ou mot de passe incorrect.';
    case 409:
      return 'Cet email est déjà utilisé.';
    case 422:
      return 'Données invalides (email incorrect ou mot de passe trop court).';
    case 429:
      return `Trop de tentatives, réessayez dans ${retryDelay(err)}.`;
    default:
      return 'Erreur inattendue, réessaie plus tard.';
  }
}

/** Délai de l'en-tête Retry-After (en secondes), arrondi à la minute supérieure. */
function retryDelay(err: HttpErrorResponse): string {
  const seconds = Number(err.headers?.get('Retry-After'));
  if (!Number.isFinite(seconds) || seconds <= 0) return 'quelques minutes';
  const minutes = Math.ceil(seconds / 60);
  return minutes === 1 ? '1 min' : `${minutes} min`;
}
