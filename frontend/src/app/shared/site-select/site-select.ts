import { Component, input, output } from '@angular/core';
import { SITE_IDS } from '../../core/sites';

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
        @for (id of sites; track id) {
          <option [value]="id">{{ id }}</option>
        }
      </select>
    </label>
  `,
})
export class SiteSelect {
  readonly value = input('');
  readonly changed = output<string>();
  protected readonly sites = SITE_IDS;
}
