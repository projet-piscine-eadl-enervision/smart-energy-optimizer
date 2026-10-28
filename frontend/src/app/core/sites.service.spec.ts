import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Site } from './models';
import { SitesService } from './sites.service';

const site: Site = {
  site_id: 'SITE001',
  site_name: 'Site 1',
  site_type: 'office',
  location: 'Nantes',
  capacity_kw: 500,
  status: 'active',
  last_consumption_kw: 42,
  last_reading_age_minutes: 1,
  last_quality: 'good',
};

describe('SitesService', () => {
  let service: SitesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SitesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('loadSites charge la liste une seule fois', () => {
    service.loadSites();
    service.loadSites();

    httpMock.expectOne('/api/sites').flush([site]);

    expect(service.sites()).toEqual([site]);
    service.loadSites();
    httpMock.expectNone('/api/sites');
  });

  it('loadSites laisse la liste vide en cas d’échec et permet de réessayer', () => {
    service.loadSites();
    httpMock.expectOne('/api/sites').flush('boom', { status: 500, statusText: 'Server Error' });

    expect(service.sites()).toEqual([]);

    service.loadSites();
    httpMock.expectOne('/api/sites').flush([site]);
    expect(service.sites()).toEqual([site]);
  });

  it('getConsumption transmet la période et la fenêtre', () => {
    service.getConsumption('SITE002', 'week', 90).subscribe();

    const req = httpMock.expectOne((r) => r.url === '/api/sites/SITE002/consumption');
    expect(req.request.params.get('period')).toBe('week');
    expect(req.request.params.get('days')).toBe('90');
    req.flush([]);
  });

  it('getConsumption laisse l’API choisir la fenêtre par défaut', () => {
    service.getConsumption('SITE002', 'day').subscribe();

    const req = httpMock.expectOne((r) => r.url === '/api/sites/SITE002/consumption');
    expect(req.request.params.has('days')).toBe(false);
    req.flush([]);
  });

  it('getQuality demande 7 jours par défaut', () => {
    service.getQuality('SITE003').subscribe();

    const req = httpMock.expectOne((r) => r.url === '/api/sites/SITE003/quality');
    expect(req.request.params.get('days')).toBe('7');
    req.flush({});
  });
});
