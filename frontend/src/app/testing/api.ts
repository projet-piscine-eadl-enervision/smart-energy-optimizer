import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

/** Réponse en erreur HTTP pour une URL : `new Failure(500)`. */
export class Failure {
  constructor(readonly status: number) {}
}

/**
 * Les vrais services et le vrai client HTTP d'Angular : seul le réseau est remplacé.
 * Les tests vérifient donc les chemins et les paramètres réellement envoyés à l'API.
 */
export function apiProviders() {
  return [provideHttpClient(), provideHttpClientTesting()];
}

/**
 * Répond à toutes les requêtes en attente, selon leur chemin (sans paramètres), et renvoie les
 * requêtes vues avec leurs paramètres, par exemple `/api/predictions?hours=24`.
 * Une requête sans réponse prévue fait échouer le test : elle n'était pas attendue.
 */
export function answer(bodies: Record<string, unknown>): string[] {
  const http = TestBed.inject(HttpTestingController);
  const seen: string[] = [];
  for (const request of http.match(() => true)) {
    // Une requête annulée (forkJoin après une erreur) n'a plus de réponse à recevoir
    if (request.cancelled) continue;
    const body = bodies[request.request.url];
    if (body === undefined) {
      throw new Error(`Requête inattendue : ${request.request.urlWithParams}`);
    }
    seen.push(request.request.urlWithParams);
    if (body instanceof Failure) {
      request.flush({ detail: 'erreur' }, { status: body.status, statusText: 'erreur' });
    } else {
      request.flush(body);
    }
  }
  return seen;
}
