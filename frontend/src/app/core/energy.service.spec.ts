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

  it('getPredictions appelle /api/predictions', () => {
    const predictions = [
      { timestamp: '2026-10-23T10:00:00Z', predicted_kw: 12.5, confidence: 0.9 },
    ];
    let received: unknown;
    service.getPredictions().subscribe((data) => (received = data));

    const req = httpMock.expectOne('/api/predictions');
    expect(req.request.method).toBe('GET');
    req.flush(predictions);

    expect(received).toEqual(predictions);
  });

  it('getHistory demande 7 jours par défaut', () => {
    service.getHistory().subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/history');
    expect(req.request.params.get('days')).toBe('7');
    req.flush([]);
  });

  it('getHistory transmet le nombre de jours demandé', () => {
    service.getHistory(1).subscribe();
    const req = httpMock.expectOne('/api/history?days=1');
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('getRecommendations appelle /api/recommendations', () => {
    service.getRecommendations().subscribe();
    const req = httpMock.expectOne('/api/recommendations');
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });
});
