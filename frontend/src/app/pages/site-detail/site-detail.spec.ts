import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { answer, apiProviders, Failure } from '../../testing/api';
import { SiteDetail } from './site-detail';

const POINTS = [{ timestamp: '2026-10-26T00:00:00Z', energy_kwh: 1200.5, max_kw: 80 }];
const QUALITY = {
  site_id: 'SITE003',
  days: 7,
  readings: 1000,
  missing_ratio: 0.05,
  by_quality: { good: 900, partial: 60, degraded: 30, critical: 10 },
  sensor_outages: 3,
};
const ROUTES = {
  '/api/sites/SITE003/consumption': POINTS,
  '/api/sites/SITE003/quality': QUALITY,
};

describe('SiteDetail', () => {
  /** Le site vient de l'adresse /sites/SITE003 : on passe par le vrai routeur. */
  async function render(routes: Record<string, unknown> = ROUTES) {
    await TestBed.configureTestingModule({
      providers: [...apiProviders(), provideRouter([{ path: 'sites/:id', component: SiteDetail }])],
    }).compileComponents();
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/sites/SITE003', SiteDetail);
    const requests = answer(routes);
    await harness.fixture.whenStable();
    harness.detectChanges();
    const element: HTMLElement = harness.routeNativeElement as HTMLElement;
    return { fixture: harness.fixture, element, requests };
  }

  it('charge la consommation par jour et la qualité du site de l’adresse', async () => {
    const { element, requests } = await render();

    expect(requests).toEqual([
      '/api/sites/SITE003/consumption?period=day',
      '/api/sites/SITE003/quality?days=7',
    ]);
    expect(element.querySelector('h2')!.textContent).toContain('SITE003');
    expect(element.querySelector('canvas')).not.toBeNull();
  });

  it('résume la qualité des relevés', async () => {
    const { element } = await render();

    expect(element.textContent).toContain('1,000 relevés sur 7 jours');
    expect(element.textContent).toContain('Consommation manquante : 5 %');
    expect(element.textContent).toContain('good');
    expect(element.textContent).toContain('900');
    expect(element.textContent).toContain('Pannes de capteur : 3');
  });

  it('recharge la consommation sur la période choisie', async () => {
    const { fixture, element } = await render();
    Array.from(element.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Mois')!
      .click();
    const requests = answer(ROUTES);
    await fixture.whenStable();

    expect(requests).toEqual([
      '/api/sites/SITE003/consumption?period=month',
      '/api/sites/SITE003/quality?days=7',
    ]);
  });

  it('indique l’absence de mesure sur la période', async () => {
    const { element } = await render({ ...ROUTES, '/api/sites/SITE003/consumption': [] });

    expect(element.textContent).toContain('Aucune mesure sur cette période.');
    expect(element.querySelector('canvas')).toBeNull();
  });

  it('indique un site inconnu', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/sites/SITE003/consumption': new Failure(404),
    });

    expect(element.textContent).toContain('Site inconnu.');
  });

  it('affiche un message si l’API échoue', async () => {
    const { element } = await render({ ...ROUTES, '/api/sites/SITE003/quality': new Failure(500) });

    expect(element.textContent).toContain("Impossible de charger le site depuis l'API.");
  });
});
