import { DecimalPipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Site } from '../../core/models';
import { SitesService } from '../../core/sites.service';

const QUALITY_CLASSES: Record<string, string> = {
  good: 'bg-emerald-100 text-emerald-800',
  partial: 'bg-amber-100 text-amber-800',
  degraded: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

/** Liste des sites avec leur dernière consommation et la qualité du dernier relevé. */
@Component({
  selector: 'app-sites',
  imports: [DecimalPipe, RouterLink],
  templateUrl: './sites.html',
})
export class Sites implements OnInit {
  private readonly sitesService = inject(SitesService);

  protected readonly sites = signal<Site[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.sitesService.getSites().subscribe({
      next: (sites) => {
        this.sites.set(sites);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Impossible de charger les sites depuis l'API.");
        this.loading.set(false);
      },
    });
  }

  protected qualityClass(quality: string): string {
    return QUALITY_CLASSES[quality] ?? 'bg-slate-200 text-slate-700';
  }

  /** « 3 min », « 2 h » : l'âge de la dernière mesure. */
  protected age(minutes: number | null): string {
    if (minutes === null) return '–';
    return minutes < 60 ? `${Math.round(minutes)} min` : `${Math.round(minutes / 60)} h`;
  }
}
