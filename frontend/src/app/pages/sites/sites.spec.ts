import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { answer, apiProviders, Failure } from '../../testing/api';
import { Sites } from './sites';

const SITE = {
  site_id: 'SITE001',
  site_name: 'Usine Lyon',
  site_type: 'factory',
  location: 'Lyon',
  capacity_kw: 1200,
  status: 'active',
  last_consumption_kw: 842.35,
  last_reading_age_minutes: 3.4,
  last_quality: 'good',
};

describe('Sites', () => {
  async function render(sites: unknown = [SITE]) {
    await TestBed.configureTestingModule({
      imports: [Sites],
      providers: [...apiProviders(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(Sites);
    fixture.detectChanges();
    const requests = answer({ '/api/sites': sites });
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { element, requests };
  }

  it('liste les sites avec dernière mesure, âge et qualité', async () => {
    const { element, requests } = await render();
    const row = element.querySelector('tbody tr')!;

    expect(requests).toEqual(['/api/sites']);
    expect(row.textContent).toContain('SITE001');
    expect(row.textContent).toContain('Usine Lyon');
    expect(row.textContent).toContain('Lyon');
    expect(row.textContent).toContain('1,200');
    expect(row.textContent).toContain('842.4');
    expect(row.textContent).toContain('3 min');
    expect(row.textContent).toContain('good');
    expect(row.querySelector('a')!.getAttribute('href')).toBe('/sites/SITE001');
  });

  it("affiche des tirets quand aucune mesure n'est connue", async () => {
    const { element } = await render([
      { ...SITE, last_consumption_kw: null, last_reading_age_minutes: null, last_quality: null, location: null },
    ]);
    const cells = element.querySelectorAll('tbody tr td');

    expect([2, 4, 5, 6].map((i) => cells[i].textContent?.trim())).toEqual(['–', '–', '–', '–']);
  });

  it('exprime en heures un relevé de plus d’une heure', async () => {
    const { element } = await render([{ ...SITE, last_reading_age_minutes: 150 }]);

    expect(element.querySelector('tbody tr')!.textContent).toContain('3 h');
  });

  it("indique l'absence de site", async () => {
    const { element } = await render([]);

    expect(element.textContent).toContain('Aucun site.');
  });

  it('affiche un message si l’API échoue', async () => {
    const { element } = await render(new Failure(500));

    expect(element.textContent).toContain("Impossible de charger les sites depuis l'API.");
  });
});
