import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../core/auth.service';
import { EnergyService } from '../../core/energy.service';
import { User } from '../../core/models';
import { Dashboard } from './dashboard';

describe('Dashboard', () => {
  const user: User = {
    id: 1,
    email: 'a@b.fr',
    is_active: true,
    role: 'admin',
    created_at: '2026-10-23T00:00:00Z',
  };
  const authStub = { me: vi.fn<() => Observable<User>>(), logout: vi.fn() };
  const energyStub = {
    getPredictions: vi.fn(() =>
      of([{ timestamp: '2026-10-23T10:00:00Z', predicted_kw: 12.34, confidence: 0.9 }]),
    ),
    getHistory: vi.fn((_days?: number) =>
      of([{ timestamp: '2026-10-23T09:00:00Z', consumption_kw: 8 }]),
    ),
    getRecommendations: vi.fn(() =>
      of([
        { id: 1, title: 'Décaler le chauffage', message: 'Avant 8 h', estimated_saving_kw: 2.5 },
      ]),
    ),
  };

  async function render(): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: AuthService, useValue: authStub },
        { provide: EnergyService, useValue: energyStub },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(Dashboard);
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  beforeEach(() => {
    authStub.me.mockReset().mockReturnValue(of(user));
    authStub.logout.mockReset();
    energyStub.getHistory.mockClear();
  });

  it("affiche l'utilisateur et les données de l'API", async () => {
    const element = await render();

    expect(element.textContent).toContain('a@b.fr');
    expect(element.textContent).toContain('admin');
    expect(element.textContent).toContain('12.3 kW');
    expect(element.textContent).toContain('90%');
    expect(element.textContent).toContain('Décaler le chauffage');
    expect(element.textContent).toContain('2.5 kW');
    expect(element.textContent).toContain('8.0 kW');
    expect(element.textContent).not.toContain('Chargement');
  });

  it("demande l'historique des dernières 24 h", async () => {
    await render();
    expect(energyStub.getHistory).toHaveBeenCalledWith(1);
  });

  it('affiche un message si une requête échoue', async () => {
    authStub.me.mockReturnValue(throwError(() => new Error('boom')));
    const element = await render();

    expect(element.textContent).toContain("Impossible de charger les données depuis l'API.");
    expect(element.querySelectorAll('section')).toHaveLength(0);
  });

  it('le bouton Déconnexion appelle logout', async () => {
    const element = await render();
    element.querySelector('button')!.click();
    expect(authStub.logout).toHaveBeenCalledOnce();
  });
});
