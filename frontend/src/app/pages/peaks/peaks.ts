import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';

import { EnergyService } from '../../core/energy.service';
import { PeakHour } from '../../core/models';
import { SiteSelect } from '../../shared/site-select/site-select';

const HORIZONS = [24, 48, 72] as const;

/** Heures annoncées en pic par le modèle, avec le seuil de chaque site. */
@Component({
  selector: 'app-peaks',
  imports: [DatePipe, DecimalPipe, SiteSelect],
  templateUrl: './peaks.html',
})
export class Peaks implements OnInit {
  private readonly energy = inject(EnergyService);

  protected readonly horizons = HORIZONS;
  protected readonly siteId = signal('');
  protected readonly hours = signal<number>(24);
  protected readonly peaks = signal<PeakHour[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  protected selectSite(siteId: string): void {
    this.siteId.set(siteId);
    this.load();
  }

  protected selectHorizon(hours: number): void {
    this.hours.set(hours);
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.energy.getPeaks(this.hours(), this.siteId() || undefined).subscribe({
      next: (peaks) => {
        this.peaks.set(peaks);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Impossible de charger les pics depuis l'API.");
        this.loading.set(false);
      },
    });
  }
}
