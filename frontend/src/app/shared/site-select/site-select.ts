import { Component, inject, input, OnInit, output } from '@angular/core';
import { SitesService } from '../../core/sites.service';

/** Choix d'un site ; la valeur vide désigne le total des sites. */
@Component({
  selector: 'app-site-select',
  template: `
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
  `,
})
export class SiteSelect implements OnInit {
  protected readonly sitesService = inject(SitesService);
  readonly value = input('');
  readonly changed = output<string>();

  ngOnInit(): void {
    this.sitesService.loadSites();
  }
}
