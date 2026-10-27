import { TestBed } from '@angular/core/testing';
import { answer, apiProviders, Failure } from '../../testing/api';
import { SiteSelect } from './site-select';

const SITES = [
  { site_id: 'SITE001', site_name: 'Usine Lyon' },
  { site_id: 'SITE002', site_name: 'Bureau Paris' },
];

describe('SiteSelect', () => {
  async function render(sites: unknown = SITES) {
    await TestBed.configureTestingModule({ imports: [SiteSelect], providers: apiProviders() }).compileComponents();
    const fixture = TestBed.createComponent(SiteSelect);
    fixture.detectChanges();
    const requests = answer({ '/api/sites': sites });
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, requests, element: fixture.nativeElement as HTMLElement };
  }

  it('propose le total puis les sites de l’API', async () => {
    const { element, requests } = await render();
    const options = Array.from(element.querySelectorAll('option')).map((o) => o.textContent?.trim());

    expect(requests).toEqual(['/api/sites']);
    expect(options).toEqual(['Tous les sites', 'SITE001 · Usine Lyon', 'SITE002 · Bureau Paris']);
  });

  it('reste utilisable avec le seul total si la liste ne se charge pas', async () => {
    const { element } = await render(new Failure(500));

    expect(Array.from(element.querySelectorAll('option')).map((o) => o.textContent?.trim())).toEqual([
      'Tous les sites',
    ]);
  });

  it('émet le site choisi, et une valeur vide pour le total', async () => {
    const { fixture, element } = await render();
    const emitted: string[] = [];
    fixture.componentInstance.changed.subscribe((v: string) => emitted.push(v));
    const select = element.querySelector('select')!;

    select.value = 'SITE002';
    select.dispatchEvent(new Event('change'));
    select.value = '';
    select.dispatchEvent(new Event('change'));

    expect(emitted).toEqual(['SITE002', '']);
  });
});
