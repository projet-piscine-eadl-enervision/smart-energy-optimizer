import { HttpClient, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, PLATFORM_ID, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Observable } from 'rxjs';
import { API_URL } from './api.config';
import { Alert, AlertStatus } from './models';

/** Délai entre deux interrogations : le collecteur tourne toutes les 60 s. */
export const ALERTS_POLL_MS = 30_000;

/**
 * Alertes des sites. Tant qu'il est démarré (depuis la page des connectés), le service interroge
 * l'API et tient à jour les alertes actives, dont le nombre alimente le badge de l'en-tête.
 * Le sondage ne tourne que dans le navigateur : sur le serveur SSR, un minuteur empêcherait le rendu
 * de se terminer.
 */
@Injectable({ providedIn: 'root' })
export class AlertsService {
  private readonly http = inject(HttpClient);
  private readonly isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly active = signal<Alert[]>([]);
  readonly activeCount = computed(() => this.active().length);
  /** Vrai si le dernier sondage a échoué : le badge peut être périmé. */
  readonly failed = signal(false);

  start(): void {
    if (!this.isBrowser || this.timer !== null) return;
    this.refresh();
    this.timer = setInterval(() => this.refresh(), ALERTS_POLL_MS);
  }

  stop(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
    this.active.set([]);
    this.failed.set(false);
  }

  refresh(): void {
    this.getAlerts({ status: 'active', limit: 200 }).subscribe({
      next: (alerts) => {
        this.active.set(alerts);
        this.failed.set(false);
      },
      error: () => this.failed.set(true),
    });
  }

  getAlerts(filters: { siteId?: string; status?: AlertStatus | 'all'; limit?: number } = {}): Observable<Alert[]> {
    let params = new HttpParams().set('status', filters.status ?? 'active').set('limit', filters.limit ?? 50);
    if (filters.siteId) params = params.set('site_id', filters.siteId);
    return this.http.get<Alert[]>(`${API_URL}/alerts`, { params });
  }
}
