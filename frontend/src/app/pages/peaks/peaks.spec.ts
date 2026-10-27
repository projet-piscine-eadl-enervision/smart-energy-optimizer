import { TestBed } from '@angular/core/testing';
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
    await TestBed.configureTestingModule({ imports: [Peaks], providers: apiProviders() }).compileComponents();
    const fixture = TestBed.createComponent(Peaks);
    fixture.detectChanges();
    const requests = answer(routes);
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { fixture, element, requests };
  }

  it('liste les pics avec le seuil et le dépassement', async () => {
    const { element, requests } = await render();
    const row = element.querySelector('tbody tr')!.textContent!;

    expect(row).toContain('SITE003');
    expect(row).toContain('120.5');
    expect(row).toContain('100.0');
    expect(row).toContain('20.5');
    expect(requests).toContain('/api/predictions/peaks?hours=24');
  });

  it('affiche un tiret quand le seuil est inconnu', async () => {
    const { element } = await render({
      ...ROUTES,
      '/api/predictions/peaks': [{ ...PEAK, threshold_kw: null, excess_kw: null }],
    });

    expect(element.querySelector('tbody tr')!.textContent).toContain('–');
  });

  it("indique l'absence de pic", async () => {
    const { element } = await render({ ...ROUTES, '/api/predictions/peaks': [] });

    expect(element.textContent).toContain('Aucun pic prévu');
    expect(element.querySelector('table')).toBeNull();
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
