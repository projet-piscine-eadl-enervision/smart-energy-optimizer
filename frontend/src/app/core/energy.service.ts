import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_URL } from './api.config';
import { ConsumptionPoint, PeakHour, Prediction, Recommendation } from './models';

/**
 * Données énergétiques. Le jeton est ajouté automatiquement par authInterceptor.
 * Sans `siteId`, l'API renvoie le total des sites.
 */
@Injectable({ providedIn: 'root' })
export class EnergyService {
  private readonly http = inject(HttpClient);

  getPredictions(hours = 24, siteId?: string): Observable<Prediction[]> {
    return this.http.get<Prediction[]>(`${API_URL}/predictions`, {
      params: this.params({ hours }, siteId),
    });
  }

  getPeaks(hours = 24, siteId?: string): Observable<PeakHour[]> {
    return this.http.get<PeakHour[]>(`${API_URL}/predictions/peaks`, {
      params: this.params({ hours }, siteId),
    });
  }

  getHistory(days = 7, siteId?: string): Observable<ConsumptionPoint[]> {
    return this.http.get<ConsumptionPoint[]>(`${API_URL}/history`, {
      params: this.params({ days }, siteId),
    });
  }

  getRecommendations(hours = 24, siteId?: string): Observable<Recommendation[]> {
    return this.http.get<Recommendation[]>(`${API_URL}/recommendations`, {
      params: this.params({ hours }, siteId),
    });
  }

  private params(base: Record<string, number>, siteId?: string): HttpParams {
    const params = new HttpParams({ fromObject: base });
    return siteId ? params.set('site_id', siteId) : params;
  }
}
