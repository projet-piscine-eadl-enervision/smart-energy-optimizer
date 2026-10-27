import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PLATFORM_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Alert } from './models';
import { AlertsService, ALERTS_POLL_MS } from './alerts.service';

const alert: Alert = {
  alert_id: 'ALR-SITE001-1',
  timestamp: '2026-10-27T10:00:00Z',
  received_at: '2026-10-27T10:01:00Z',
  site_id: 'SITE001',
  site_name: 'Site 1',
  severity: 'high',
  alert_type: 'threshold',
  alert_label: 'Dépassement du seuil',
  message: null,
  value: 130,
  threshold: 117,
  origin: 'api',
  status: 'active',
};

describe('AlertsService', () => {
  let httpMock: HttpTestingController;

  function setup(platform = 'browser'): AlertsService {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PLATFORM_ID, useValue: platform },
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    return TestBed.inject(AlertsService);
  }

  const pending = () => httpMock.match((r) => r.url === '/api/alerts');

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    TestBed.inject(AlertsService).stop();
    vi.useRealTimers();
  });

  it('start interroge les alertes actives et compte les résultats', () => {
    const service = setup();
    service.start();

    const [req] = pending();
    expect(req.request.params.get('status')).toBe('active');
    expect(req.request.params.get('limit')).toBe('200');
    req.flush([alert, { ...alert, alert_id: 'ALR-SITE002-1' }]);

    expect(service.active()).toHaveLength(2);
    expect(service.activeCount()).toBe(2);
    expect(service.failed()).toBe(false);
  });

  it('réinterroge toutes les 30 secondes', () => {
    const service = setup();
    service.start();
    pending()[0].flush([]);

    vi.advanceTimersByTime(ALERTS_POLL_MS - 1);
    expect(pending()).toHaveLength(0);

    vi.advanceTimersByTime(1);
    const requests = pending();
    expect(requests).toHaveLength(1);
    requests[0].flush([alert]);
    expect(service.activeCount()).toBe(1);
  });

  it('un second start ne double pas le sondage', () => {
    const service = setup();
    service.start();
    service.start();

    expect(pending()).toHaveLength(1);
  });

  it('stop arrête le sondage et vide les alertes', () => {
    const service = setup();
    service.start();
    pending()[0].flush([alert]);

    service.stop();
    vi.advanceTimersByTime(ALERTS_POLL_MS * 3);

    expect(pending()).toHaveLength(0);
    expect(service.activeCount()).toBe(0);
  });

  it('un échec garde les alertes connues et lève le drapeau failed', () => {
    const service = setup();
    service.start();
    pending()[0].flush([alert]);

    vi.advanceTimersByTime(ALERTS_POLL_MS);
    pending()[0].flush('boom', { status: 500, statusText: 'Server Error' });

    expect(service.failed()).toBe(true);
    expect(service.activeCount()).toBe(1);
  });

  it('ne sonde pas côté serveur', () => {
    const service = setup('server');
    service.start();
    vi.advanceTimersByTime(ALERTS_POLL_MS * 2);

    expect(pending()).toHaveLength(0);
  });

  it('getAlerts transmet le site, l’état et la limite', () => {
    const service = setup();
    service.getAlerts({ siteId: 'SITE003', status: 'all', limit: 10 }).subscribe();

    const [req] = pending();
    expect(req.request.params.get('site_id')).toBe('SITE003');
    expect(req.request.params.get('status')).toBe('all');
    expect(req.request.params.get('limit')).toBe('10');
    req.flush([]);
  });
});
