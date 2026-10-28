import { TestBed } from '@angular/core/testing';
import { answer, apiProviders, Failure } from '../../testing/api';
import { Alerts } from './alerts';

const ALERT = {
  alert_id: 'ALR-SITE006-1',
  timestamp: '2026-10-27T10:00:00Z',
  received_at: '2026-10-27T10:01:00Z',
  site_id: 'SITE006',
  site_name: 'Bureau Bordeaux',
  severity: 'medium',
  alert_type: 'threshold',
  alert_label: 'Dépassement du seuil',
  message: 'Seuil de consommation dépassé',
  value: 132.77,
  threshold: 117,
  origin: 'api',
  status: 'active',
};
const ROUTES = {
  '/api/sites': [{ site_id: 'SITE006', site_name: 'Bureau Bordeaux' }],
  '/api/alerts': [ALERT],
};

describe('Alerts', () => {
  async function render(routes: Record<string, unknown> = ROUTES) {
    await TestBed.configureTestingModule({
      imports: [Alerts],
      providers: apiProviders(),
    }).compileComponents();
    const fixture = TestBed.createComponent(Alerts);
    fixture.detectChanges();
    const requests = answer(routes);
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { fixture, element, requests };
  }

  it('liste les alertes actives avec leur site, leur valeur et leur seuil', async () => {
    const { element, requests } = await render();

    expect(element.textContent).toContain('Dépassement du seuil');
    expect(element.textContent).toContain('SITE006 · Bureau Bordeaux');
    expect(element.textContent).toContain('Seuil de consommation dépassé');
    expect(element.textContent).toContain('valeur 132.8');
    expect(element.textContent).toContain('seuil 117.0');
    expect(requests).toContain('/api/alerts?status=active&limit=100');
  });

  it('marque une alerte résolue', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/alerts': [{ ...ALERT, status: 'resolved' }],
    });

    expect(element.textContent).toContain('résolue');
  });

  it("recharge selon l'état choisi", async () => {
    const { fixture, element } = await render();
    Array.from(element.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Toutes')!
      .click();
    const requests = answer(ROUTES);
    await fixture.whenStable();

    expect(requests).toEqual(['/api/alerts?status=all&limit=100']);
  });

  it('recharge selon le site choisi', async () => {
    const { fixture, element } = await render();
    const select = element.querySelector('select')!;
    select.value = 'SITE006';
    select.dispatchEvent(new Event('change'));
    const requests = answer(ROUTES);
    await fixture.whenStable();

    expect(requests).toEqual(['/api/alerts?status=active&limit=100&site_id=SITE006']);
  });

  it("indique l'absence d'alerte", async () => {
    const { element } = await render({ ...ROUTES, '/api/alerts': [] });

    expect(element.textContent).toContain('Aucune alerte.');
  });

  it("affiche un message si l'API échoue", async () => {
    const { element } = await render({ ...ROUTES, '/api/alerts': new Failure(500) });

    expect(element.textContent).toContain("Impossible de charger les alertes depuis l'API.");
  });
});
