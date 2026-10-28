import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { answer, apiProviders, Failure } from '../../testing/api';
import { Peaks } from './peaks';

const PEAK = {
  timestamp: '2026-10-23T19:00:00Z',
  site_id: 'SITE003',
  predicted_kw: 120.5,
  threshold_kw: 100,
  excess_kw: 20.5,
  model_version: '1',
};
const ROUTES = {
  '/api/sites': [{ site_id: 'SITE001', site_name: 'Site 1' }],
  '/api/predictions/peaks': [PEAK],
};

describe('Peaks', () => {
  async function render(routes: Record<string, unknown> = ROUTES) {
    await TestBed.configureTestingModule({ imports: [Peaks], providers: [...apiProviders(), provideRouter([])] }).compileComponents();
    const fixture = TestBed.createComponent(Peaks);
    fixture.detectChanges();
    const requests = answer(routes);
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { fixture, element, requests };
  }

  /** Un pic dans `hoursAhead` heures, pour que la frise et le jour affiché soient ceux d'aujourd'hui. */
  function peakIn(hoursAhead: number, overrides = {}) {
    const hour = Math.floor(Date.now() / 3_600_000) * 3_600_000;
    return { ...PEAK, timestamp: new Date(hour + hoursAhead * 3_600_000).toISOString(), ...overrides };
  }

  it('liste les pics avec le site, le seuil et le dépassement', async () => {
    const { element, requests } = await render();
    const row = element.querySelector('li')!.textContent!;

    expect(row).toContain('SITE003');
    expect(row).toContain('120.5 kW');
    expect(row).toContain('seuil de 100.0 kW');
    expect(row).toContain('+21 % (20.5 kW)');
    expect(requests).toContain('/api/predictions/peaks?hours=24');
  });

  it('nomme le site quand il est connu', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/sites': [{ site_id: 'SITE003', site_name: 'Entrepôt Lyon' }],
    });

    expect(element.querySelector('li')!.textContent).toContain('SITE003 · Entrepôt Lyon');
  });

  it('résume le nombre de pics, de sites et le plus fort dépassement', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/predictions/peaks': [
        peakIn(2, { site_id: 'SITE001', excess_kw: 5, threshold_kw: 100 }),
        peakIn(3, { site_id: 'SITE003', excess_kw: 40, threshold_kw: 100 }),
        peakIn(4, { site_id: 'SITE003', excess_kw: 10, threshold_kw: 100 }),
      ],
    });
    const text = element.textContent!;

    expect(text).toMatch(/3\s*heures de pic prévues/);
    expect(text).toMatch(/2\s*sites concernés/);
    expect(text).toContain('+40 %');
    expect(text).toContain('SITE003');
  });

  it('regroupe les pics par jour et colore la frise du site', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/predictions/peaks': [peakIn(1), peakIn(2), peakIn(23)],
    });
    const titles = Array.from(element.querySelectorAll('section h3')).map((h) => h.textContent!);
    const colored = element.querySelectorAll('span[title*="kW prévus"]');

    expect(titles.filter((t) => /^(Aujourd'hui|Demain)/.test(t)).length).toBeGreaterThan(0);
    expect(colored.length).toBe(3);
  });

  it('indique un seuil non défini quand il est inconnu', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/predictions/peaks': [{ ...PEAK, threshold_kw: null, excess_kw: null }],
    });

    expect(element.querySelector('li')!.textContent).toContain('seuil non défini');
  });

  it("indique l'absence de pic", async () => {
    const { element } = await render({ ...ROUTES, '/api/predictions/peaks': [] });

    expect(element.textContent).toContain('Aucun pic prévu');
    expect(element.querySelector('li')).toBeNull();
  });

  it("recharge sur l'horizon et le site choisis", async () => {
    const { fixture, element } = await render();
    const select = element.querySelector('select')!;
    select.value = 'SITE001';
    select.dispatchEvent(new Event('change'));
    Array.from(element.querySelectorAll('button')).find((b) => b.textContent?.trim() === '72 h')!.click();
    const requests = answer(ROUTES);
    await fixture.whenStable();

    expect(requests).toEqual([
      '/api/predictions/peaks?hours=24&site_id=SITE001',
      '/api/predictions/peaks?hours=72&site_id=SITE001',
    ]);
  });

  it("affiche un message si l'API échoue", async () => {
    const { element } = await render({ ...ROUTES, '/api/predictions/peaks': new Failure(500) });

    expect(element.textContent).toContain("Impossible de charger les pics depuis l'API.");
  });
});
