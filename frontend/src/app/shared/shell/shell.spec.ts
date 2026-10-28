import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { answer, apiProviders, Failure } from '../../testing/api';
import { Shell } from './shell';

const USER = { id: 1, email: 'a@b.fr', is_active: true, role: 'admin', created_at: '2026-10-23T00:00:00Z' };
const ALERT = {
  alert_id: 'ALR-SITE001-1',
  timestamp: '2026-10-27T10:00:00Z',
  received_at: '2026-10-27T10:01:00Z',
  site_id: 'SITE001',
  site_name: 'Site 1',
  severity: 'high',
  alert_type: 'threshold',
  alert_label: 'Dépassement du seuil',
  message: null,
  value: null,
  threshold: null,
  origin: 'api',
  status: 'active',
};
const ROUTES = { '/api/auth/me': USER, '/api/alerts': [] };

describe('Shell', () => {
  async function render(routes: Record<string, unknown> = ROUTES) {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [...apiProviders(), provideRouter([{ path: 'login', children: [] }])],
    }).compileComponents();
    const fixture = TestBed.createComponent(Shell);
    fixture.detectChanges();
    // Le compte d'abord, puis les alertes, qui ne partent qu'une fois le compte connu
    const requests = answer(routes);
    await fixture.whenStable();
    requests.push(...answer(routes));
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    return { fixture, element, requests };
  }

  beforeEach(() => localStorage.setItem('enervision_token', 'jeton-de-test'));
  afterEach(() => localStorage.removeItem('enervision_token'));

  it("affiche l'utilisateur et son rôle", async () => {
    const { element } = await render();
    const header = element.querySelector('header')!;

    expect(header.textContent).toContain('Smart Energy Optimizer');
    expect(header.textContent).toContain('a@b.fr');
    expect(header.textContent).toContain('admin');
  });

  it('propose les pages de l’application', async () => {
    const { element } = await render();
    const links = Array.from(element.querySelectorAll('nav a')).map((a) => ({
      text: a.textContent?.replace(/\s+/g, ' ').trim(),
      href: a.getAttribute('href'),
    }));

    expect(links).toEqual([
      { text: 'Tableau de bord', href: '/' },
      { text: 'Sites', href: '/sites' },
      { text: 'Pics prévus', href: '/peaks' },
      { text: 'Alertes', href: '/alerts' },
    ]);
  });

  it('interroge les alertes actives dès l’affichage', async () => {
    const { requests } = await render();

    expect(requests).toEqual(['/api/auth/me', '/api/alerts?status=active&limit=200']);
  });

  it("affiche le nombre d'alertes actives dans un badge", async () => {
    const { element } = await render({ ...ROUTES, '/api/alerts': [ALERT, { ...ALERT, alert_id: 'x' }, ALERT] });

    expect(element.querySelector('nav a[href="/alerts"]')!.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'Alertes 3',
    );
  });

  it("n'affiche pas de badge sans alerte active", async () => {
    const { element } = await render();

    expect(element.querySelector('nav a[href="/alerts"]')!.textContent?.trim()).toBe('Alertes');
  });

  it("reste utilisable si la requête du compte échoue", async () => {
    const { element } = await render({ ...ROUTES, '/api/auth/me': new Failure(500) });

    expect(element.querySelector('nav')).not.toBeNull();
    expect(element.querySelector('header')!.textContent).not.toContain('a@b.fr');
  });

  it("affiche le site d'un user rattaché à un site", async () => {
    const { element, requests } = await render({
      ...ROUTES,
      '/api/auth/me': { ...USER, role: 'user', site_id: 'SITE001' },
    });

    expect(element.querySelector('header')!.textContent).toContain('SITE001');
    expect(requests).toContain('/api/alerts?status=active&limit=200');
  });

  it("explique à un user sans site qu'il doit en demander un, sans interroger les données", async () => {
    const { element, requests } = await render({
      ...ROUTES,
      '/api/auth/me': { ...USER, role: 'user', site_id: null },
    });

    expect(element.querySelector('main')!.textContent).toContain('Aucun site');
    expect(element.querySelector('router-outlet')).toBeNull();
    expect(requests).toEqual(['/api/auth/me']);
  });

  it('Déconnexion efface le jeton et renvoie vers /login', async () => {
    const { fixture, element } = await render();
    element.querySelector<HTMLButtonElement>('header button')!.click();
    await fixture.whenStable();

    expect(localStorage.getItem('enervision_token')).toBeNull();
    expect(TestBed.inject(Router).url).toBe('/login');
  });
});
