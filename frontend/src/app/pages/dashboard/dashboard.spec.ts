import { TestBed } from '@angular/core/testing';
import { answer, apiProviders, Failure } from '../../testing/api';
import { Dashboard } from './dashboard';

const SITES = [
  { site_id: 'SITE003', site_name: 'Site 3' },
  { site_id: 'SITE004', site_name: 'Site 4' },
];
const PREDICTIONS = [
  { timestamp: '2026-10-23T10:00:00Z', site_id: 'ALL', predicted_kw: 12.34, is_peak: null, model_version: '1' },
  { timestamp: '2026-10-23T11:00:00Z', site_id: 'ALL', predicted_kw: 20, is_peak: null, model_version: '1' },
];
const HISTORY = [{ timestamp: '2026-10-23T09:00:00Z', consumption_kw: 8 }];
const RECOMMENDATIONS = [
  {
    id: 1,
    title: 'Décaler le chauffage',
    message: 'Avant 8 h',
    estimated_saving_kw: 2.5,
    site_id: 'SITE003',
    target_time: '2026-10-23T11:00:00Z',
    alert_type: 'threshold',
  },
  {
    id: 2,
    title: 'Alerte capteur',
    message: 'Capteur muet',
    estimated_saving_kw: null,
    site_id: 'SITE001',
    target_time: '2026-10-23T12:00:00Z',
    alert_type: 'sensor',
  },
];
const ROUTES = {
  '/api/sites': SITES,
  '/api/predictions': PREDICTIONS,
  '/api/history': HISTORY,
  '/api/recommendations': RECOMMENDATIONS,
};

describe('Dashboard', () => {
  async function render(routes: Record<string, unknown> = ROUTES) {
    await TestBed.configureTestingModule({ imports: [Dashboard], providers: apiProviders() }).compileComponents();
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    const requests = answer(routes);
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { fixture, element, requests };
  }

  it("affiche les trois sections et les recommandations de l'API", async () => {
    const { element } = await render();
    const titles = Array.from(element.querySelectorAll('section h2')).map((h) => h.textContent?.trim());

    expect(titles).toEqual(['Prédictions de la consommation', 'Historique (24 h)', 'Recommandations']);
    expect(element.querySelectorAll('section canvas')).toHaveLength(2);
    expect(element.textContent).toContain('Décaler le chauffage');
    expect(element.textContent).toContain('Économie estimée : 2.5 kW');
    expect(element.textContent).not.toContain('Chargement');
  });

  it("demande à l'API le total des sites sur 24 h", async () => {
    const { requests } = await render();

    expect(requests).toContain('/api/predictions?hours=24');
    expect(requests).toContain('/api/history?days=1');
    expect(requests).toContain('/api/recommendations?hours=24');
    expect(requests).toContain('/api/sites');
  });

  it("n'affiche pas d'économie pour une recommandation sans estimation", async () => {
    const { element } = await render();

    expect(element.textContent).toContain('Alerte capteur');
    expect(element.textContent?.match(/Économie estimée/g)).toHaveLength(1);
  });

  it('affiche le site de chaque recommandation', async () => {
    const { element } = await render();

    expect(element.textContent).toContain('SITE003');
    expect(element.textContent).toContain('SITE001');
  });

  it('propose les sites de l’API dans le sélecteur', async () => {
    const { element } = await render();
    const options = Array.from(element.querySelectorAll('option')).map((o) => o.textContent?.trim());

    expect(options).toEqual(['Tous les sites', 'SITE003 · Site 3', 'SITE004 · Site 4']);
  });

  it('recharge les données du site choisi', async () => {
    const { fixture, element } = await render();
    const select = element.querySelector('select')!;
    select.value = 'SITE004';
    select.dispatchEvent(new Event('change'));
    const requests = answer(ROUTES);
    await fixture.whenStable();

    expect(requests).toEqual(
      expect.arrayContaining([
        '/api/predictions?hours=24&site_id=SITE004',
        '/api/history?days=1&site_id=SITE004',
        '/api/recommendations?hours=24&site_id=SITE004',
      ]),
    );
  });

  it("recharge l'historique sur la période choisie", async () => {
    const { fixture, element } = await render();
    Array.from(element.querySelectorAll('button')).find((b) => b.textContent?.trim() === '7 jours')!.click();
    const requests = answer(ROUTES);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(requests).toContain('/api/history?days=7');
    expect(element.textContent).toContain('Historique (7 jours)');
  });

  it('affiche la légende des pics quand un site a un pic prévu', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/predictions': [{ ...PREDICTIONS[0], site_id: 'SITE003', is_peak: true }],
    });

    expect(element.textContent).toContain('pic prévu pour le site');
  });

  it("indique l'absence de prévision", async () => {
    const { element } = await render({ ...ROUTES, '/api/predictions': [] });

    expect(element.textContent).toContain('Aucune prévision disponible');
    expect(element.querySelectorAll('section canvas')).toHaveLength(1);
  });

  it("affiche un message si une route de données échoue", async () => {
    const { element } = await render({ ...ROUTES, '/api/predictions': new Failure(500) });

    expect(element.textContent).toContain("Impossible de charger les données depuis l'API.");
    expect(element.querySelectorAll('section')).toHaveLength(0);
  });
});
