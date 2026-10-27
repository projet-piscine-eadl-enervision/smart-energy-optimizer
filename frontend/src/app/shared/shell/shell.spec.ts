import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../core/auth.service';
import { User } from '../../core/models';
import { Shell } from './shell';

describe('Shell', () => {
  const user: User = {
    id: 1,
    email: 'a@b.fr',
    is_active: true,
    role: 'admin',
    created_at: '2026-10-23T00:00:00Z',
  };
  const authStub = { me: vi.fn<() => Observable<User>>(), logout: vi.fn() };

  async function render(): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [provideRouter([]), { provide: AuthService, useValue: authStub }],
    }).compileComponents();
    const fixture = TestBed.createComponent(Shell);
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  beforeEach(() => {
    authStub.me.mockReset().mockReturnValue(of(user));
    authStub.logout.mockReset();
  });

  it("affiche l'utilisateur et son rôle", async () => {
    const header = (await render()).querySelector('header')!;

    expect(header.textContent).toContain('Smart Energy Optimizer');
    expect(header.textContent).toContain('a@b.fr');
    expect(header.textContent).toContain('admin');
  });

  it('propose le tableau de bord et les pics prévus', async () => {
    const links = Array.from((await render()).querySelectorAll('nav a')).map((a) => ({
      text: a.textContent?.trim(),
      href: a.getAttribute('href'),
    }));

    expect(links).toEqual([
      { text: 'Tableau de bord', href: '/' },
      { text: 'Pics prévus', href: '/peaks' },
    ]);
  });

  it("reste utilisable si la requête du compte échoue", async () => {
    authStub.me.mockReturnValue(throwError(() => new Error('boom')));
    const element = await render();

    expect(element.querySelector('nav')).not.toBeNull();
    expect(element.querySelector('header')!.textContent).not.toContain('a@b.fr');
  });

  it('le bouton Déconnexion appelle logout', async () => {
    const element = await render();
    element.querySelector<HTMLButtonElement>('header button')!.click();
    expect(authStub.logout).toHaveBeenCalledOnce();
  });
});
