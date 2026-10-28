import { Component, computed, inject, input, OnInit, output } from '@angular/core';
import { AuthService } from '../../core/auth.service';
import { SitesService } from '../../core/sites.service';

/**
 * Choix d'un site ; la valeur vide désigne le total des sites.
 * Un `user` ne voit que son site : pas de choix, son site est affiché (l'API filtre déjà les données).
 */
@Component({
  selector: 'app-site-select',
  template: `
    @if (ownSite(); as site) {
      <p class="flex items-center gap-2 text-sm text-slate-600">
        Site
        <span class="rounded bg-white px-2 py-1 font-medium text-slate-800">{{ site }}</span>
      </p>
    } @else {
    <label class="flex items-center gap-2 text-sm text-slate-600">
      Site
      <select
        class="rounded border border-slate-300 bg-white px-2 py-1"
        [value]="value()"
        (change)="changed.emit($any($event.target).value)"
      >
        <option value="">Tous les sites</option>
        @for (site of sitesService.sites(); track site.site_id) {
          <option [value]="site.site_id">{{ site.site_id }} · {{ site.site_name }}</option>
        }
      </select>
    </label>
    }
  `,
})
export class SiteSelect implements OnInit {
  protected readonly sitesService = inject(SitesService);
  private readonly auth = inject(AuthService);
  readonly value = input('');

  /** Pour un `user` rattaché à un site : « SITE001 · nom » ; vide pour un admin. */
  protected readonly ownSite = computed(() => {
    const u = this.auth.user();
    if (!u || u.role === 'admin' || !u.site_id) return null;
    const site = this.sitesService.sites().find((s) => s.site_id === u.site_id);
    return site ? `${site.site_id} · ${site.site_name}` : u.site_id;
  });
  readonly changed = output<string>();

  ngOnInit(): void {
    this.sitesService.loadSites();
  }
}
