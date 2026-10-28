import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, Observable, of, tap } from 'rxjs';
import { API_URL } from './api.config';
import { Period, Site, SiteConsumptionPoint, SiteQuality } from './models';

/** Sites et leurs mesures. Le jeton est ajouté automatiquement par authInterceptor. */
@Injectable({ providedIn: 'root' })
export class SitesService {
  private readonly http = inject(HttpClient);

  /** Liste partagée par les sélecteurs de site ; vide tant qu'elle n'est pas chargée. */
  readonly sites = signal<Site[]>([]);
  private requested = false;

  /** Charge la liste une seule fois. Un échec laisse la liste vide : le total reste utilisable. */
  loadSites(): void {
    if (this.requested) return;
    this.requested = true;
    this.getSites()
      .pipe(
        tap((sites) => this.sites.set(sites)),
        catchError(() => {
          this.requested = false;
          return of([]);
        }),
      )
      .subscribe();
  }

  getSites(): Observable<Site[]> {
    return this.http.get<Site[]>(`${API_URL}/sites`);
  }

  getConsumption(
    siteId: string,
    period: Period,
    days?: number,
  ): Observable<SiteConsumptionPoint[]> {
    let params = new HttpParams().set('period', period);
    if (days) params = params.set('days', days);
    return this.http.get<SiteConsumptionPoint[]>(`${API_URL}/sites/${siteId}/consumption`, {
      params,
    });
  }

  getQuality(siteId: string, days = 7): Observable<SiteQuality> {
    return this.http.get<SiteQuality>(`${API_URL}/sites/${siteId}/quality`, {
      params: new HttpParams().set('days', days),
    });
  }
}
