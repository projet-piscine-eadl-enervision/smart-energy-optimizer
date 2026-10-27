import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { EnergyService } from '../../core/energy.service';
import { PeakHour } from '../../core/models';
import { Peaks } from './peaks';

describe('Peaks', () => {
  const peak: PeakHour = {
    timestamp: '2026-10-23T19:00:00Z',
    site_id: 'SITE003',
    predicted_kw: 120.5,
    threshold_kw: 100,
    excess_kw: 20.5,
    model_version: '1',
  };
  const energyStub = {
    getPeaks: vi.fn((_hours?: number, _siteId?: string) => of([peak])),
  };

  async function render() {
    await TestBed.configureTestingModule({
      imports: [Peaks],
      providers: [{ provide: EnergyService, useValue: energyStub }],
    }).compileComponents();
    const fixture = TestBed.createComponent(Peaks);
    await fixture.whenStable();
    return fixture;
  }

  beforeEach(() => energyStub.getPeaks.mockClear());

  it('liste les pics avec le seuil et le dépassement', async () => {
    const element: HTMLElement = (await render()).nativeElement;
    const row = element.querySelector('tbody tr')!.textContent!;

    expect(row).toContain('SITE003');
    expect(row).toContain('120.5');
    expect(row).toContain('100.0');
    expect(row).toContain('20.5');
    expect(energyStub.getPeaks).toHaveBeenCalledWith(24, undefined);
  });

  it('affiche un tiret quand le seuil est inconnu', async () => {
    energyStub.getPeaks.mockReturnValueOnce(
      of([{ ...peak, threshold_kw: null, excess_kw: null }]),
    );
    const element: HTMLElement = (await render()).nativeElement;

    expect(element.querySelector('tbody tr')!.textContent).toContain('–');
  });

  it("indique l'absence de pic", async () => {
    energyStub.getPeaks.mockReturnValueOnce(of([]));
    const element: HTMLElement = (await render()).nativeElement;

    expect(element.textContent).toContain('Aucun pic prévu');
    expect(element.querySelector('table')).toBeNull();
  });

  it("recharge sur l'horizon et le site choisis", async () => {
    const fixture = await render();
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('select');
    select.value = 'SITE001';
    select.dispatchEvent(new Event('change'));
    const button = Array.from<HTMLButtonElement>(fixture.nativeElement.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === '72 h',
    )!;
    button.click();
    await fixture.whenStable();

    expect(energyStub.getPeaks).toHaveBeenLastCalledWith(72, 'SITE001');
  });

  it("affiche un message si l'API échoue", async () => {
    energyStub.getPeaks.mockReturnValueOnce(throwError(() => new Error('500')));
    const element: HTMLElement = (await render()).nativeElement;

    expect(element.textContent).toContain("Impossible de charger les pics depuis l'API.");
  });
});
