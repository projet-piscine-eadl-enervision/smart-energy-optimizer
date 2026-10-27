import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EnergyService } from './energy.service';

describe('EnergyService', () => {
  let service: EnergyService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(EnergyService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('getPredictions demande 24 h pour le total des sites par défaut', () => {
    const predictions = [{ timestamp: '2026-10-23T10:00:00Z', predicted_kw: 12.5 }];
    let received: unknown;
    service.getPredictions().subscribe((data) => (received = data));

    const req = httpMock.expectOne((r) => r.url === '/api/predictions');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('hours')).toBe('24');
    expect(req.request.params.has('site_id')).toBe(false);
    req.flush(predictions);

    expect(received).toEqual(predictions);
  });

  it("getPredictions transmet l'horizon et le site", () => {
    service.getPredictions(48, 'SITE003').subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/predictions');
    expect(req.request.params.get('hours')).toBe('48');
    expect(req.request.params.get('site_id')).toBe('SITE003');
    req.flush([]);
  });

  it('getPeaks appelle /api/predictions/peaks', () => {
    service.getPeaks(72, 'SITE001').subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/predictions/peaks');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('hours')).toBe('72');
    expect(req.request.params.get('site_id')).toBe('SITE001');
    req.flush([]);
  });

  it('getHistory demande 7 jours par défaut', () => {
    service.getHistory().subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/history');
    expect(req.request.params.get('days')).toBe('7');
    expect(req.request.params.has('site_id')).toBe(false);
    req.flush([]);
  });

  it('getHistory transmet le nombre de jours et le site demandés', () => {
    service.getHistory(1, 'SITE002').subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/history');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('days')).toBe('1');
    expect(req.request.params.get('site_id')).toBe('SITE002');
    req.flush([]);
  });

  it('getRecommendations demande 24 h pour tous les sites par défaut', () => {
    service.getRecommendations().subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/recommendations');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('hours')).toBe('24');
    expect(req.request.params.has('site_id')).toBe(false);
    req.flush([]);
  });

  it('getRecommendations transmet le site demandé', () => {
    service.getRecommendations(24, 'SITE005').subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/recommendations');
    expect(req.request.params.get('site_id')).toBe('SITE005');
    req.flush([]);
  });
});
