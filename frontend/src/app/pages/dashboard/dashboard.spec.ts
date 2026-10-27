import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { EnergyService } from '../../core/energy.service';
import { Dashboard } from './dashboard';

describe('Dashboard', () => {
  const energyStub = {
    getPredictions: vi.fn((_hours?: number, _siteId?: string) =>
      of([
        { timestamp: '2026-10-23T10:00:00Z', predicted_kw: 12.34, is_peak: false, site_id: 'ALL', model_version: '1' },
        { timestamp: '2026-10-23T11:00:00Z', predicted_kw: 20, is_peak: true, site_id: 'ALL', model_version: '1' },
      ]),
    ),
    getHistory: vi.fn((_days?: number, _siteId?: string) =>
      of([{ timestamp: '2026-10-23T09:00:00Z', consumption_kw: 8 }]),
    ),
    getRecommendations: vi.fn((_hours?: number, _siteId?: string) =>
      of([
        {
          id: 1,
          title: 'Décaler le chauffage',
          message: 'Avant 8 h',
          estimated_saving_kw: 2.5,
          site_id: 'SITE003',
          target_time: '2026-10-23T11:00:00Z',
          alert_type: 'peak',
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
      ]),
    ),
  };

  async function render() {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [{ provide: EnergyService, useValue: energyStub }],
    }).compileComponents();
    const fixture = TestBed.createComponent(Dashboard);
    await fixture.whenStable();
    return fixture;
  }

  beforeEach(() => {
    energyStub.getPredictions.mockClear();
    energyStub.getHistory.mockClear();
    energyStub.getRecommendations.mockClear();
  });

  it('affiche les trois sections et les recommandations de l\'API', async () => {
    const element: HTMLElement = (await render()).nativeElement;
    const titles = Array.from(element.querySelectorAll('section h2')).map((h) =>
      h.textContent?.trim(),
    );

    expect(titles).toEqual([
      'Prédictions de la consommation',
      'Historique (24 h)',
      'Recommandations',
    ]);
    expect(element.querySelectorAll('section canvas')).toHaveLength(2);
    expect(element.textContent).toContain('Décaler le chauffage');
    expect(element.textContent).toContain('Économie estimée : 2.5 kW');
    expect(element.textContent).not.toContain('Chargement');
  });

  it("n'affiche pas d'économie pour une recommandation sans estimation", async () => {
    const element: HTMLElement = (await render()).nativeElement;
    expect(element.textContent).toContain('Alerte capteur');
    expect(element.textContent?.match(/Économie estimée/g)).toHaveLength(1);
  });

  it('demande par défaut le total des sites sur 24 h', async () => {
    await render();
    expect(energyStub.getPredictions).toHaveBeenCalledWith(24, undefined);
    expect(energyStub.getHistory).toHaveBeenCalledWith(1, undefined);
    expect(energyStub.getRecommendations).toHaveBeenCalledWith(24, undefined);
  });

  it('affiche le site de chaque recommandation', async () => {
    const element: HTMLElement = (await render()).nativeElement;
    expect(element.textContent).toContain('SITE003');
    expect(element.textContent).toContain('SITE001');
  });

  it('recharge les données du site choisi', async () => {
    const fixture = await render();
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('select');
    select.value = 'SITE004';
    select.dispatchEvent(new Event('change'));
    await fixture.whenStable();

    expect(energyStub.getPredictions).toHaveBeenLastCalledWith(24, 'SITE004');
    expect(energyStub.getHistory).toHaveBeenLastCalledWith(1, 'SITE004');
    expect(energyStub.getRecommendations).toHaveBeenLastCalledWith(24, 'SITE004');
  });

  it("recharge l'historique sur la période choisie", async () => {
    const fixture = await render();
    const button = Array.from<HTMLButtonElement>(fixture.nativeElement.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === '7 jours',
    )!;
    button.click();
    await fixture.whenStable();

    expect(energyStub.getHistory).toHaveBeenLastCalledWith(7, undefined);
    expect(fixture.nativeElement.textContent).toContain('Historique (7 jours)');
  });

  it("indique l'absence de prévision", async () => {
    energyStub.getPredictions.mockReturnValueOnce(of([]));
    const element: HTMLElement = (await render()).nativeElement;

    expect(element.textContent).toContain('Aucune prévision disponible');
    expect(element.querySelectorAll('section canvas')).toHaveLength(1);
  });

  it("affiche un message si une route de données échoue", async () => {
    energyStub.getPredictions.mockReturnValueOnce(throwError(() => new Error('500')));
    const element: HTMLElement = (await render()).nativeElement;

    expect(element.textContent).toContain("Impossible de charger les données depuis l'API.");
    expect(element.querySelectorAll('section')).toHaveLength(0);
  });
});
