import { DecimalPipe } from '@angular/common';
import { Component, ElementRef, inject, OnDestroy, OnInit, signal, viewChild } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Chart, registerables } from 'chart.js';

import { Period, SiteConsumptionPoint, SiteQuality } from '../../core/models';
import { SitesService } from '../../core/sites.service';

Chart.register(...registerables);

const PERIODS: { value: Period; label: string }[] = [
  { value: 'hour', label: 'Heure' },
  { value: 'day', label: 'Jour' },
  { value: 'week', label: 'Semaine' },
  { value: 'month', label: 'Mois' },
];

/** Consommation d'un site par heure, jour, semaine ou mois, et qualité de ses relevés. */
@Component({
  selector: 'app-site-detail',
  imports: [DecimalPipe, RouterLink],
  templateUrl: './site-detail.html',
})
export class SiteDetail implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly sitesService = inject(SitesService);

  private readonly canvas = viewChild<ElementRef<HTMLCanvasElement>>('consumptionChart');
  private chart: Chart | null = null;

  protected readonly periods = PERIODS;
  protected readonly siteId = signal('');
  protected readonly period = signal<Period>('day');
  protected readonly points = signal<SiteConsumptionPoint[]>([]);
  protected readonly quality = signal<SiteQuality | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.siteId.set(params.get('id') ?? '');
      this.load();
    });
  }

  protected selectPeriod(period: Period): void {
    this.period.set(period);
    this.load();
  }

  protected qualityEntries(): [string, number][] {
    return Object.entries(this.quality()?.by_quality ?? {});
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      points: this.sitesService.getConsumption(this.siteId(), this.period()),
      quality: this.sitesService.getQuality(this.siteId()),
    }).subscribe({
      next: (data) => {
        this.points.set(data.points);
        this.quality.set(data.quality);
        this.loading.set(false);
        // Le canvas n'existe qu'après le rendu de la section
        setTimeout(() => this.draw(), 0);
      },
      error: (err: { status?: number }) => {
        this.error.set(
          err.status === 404 ? 'Site inconnu.' : "Impossible de charger le site depuis l'API.",
        );
        this.loading.set(false);
      },
    });
  }

  private label(timestamp: string): string {
    const date = new Date(timestamp);
    switch (this.period()) {
      case 'hour':
        return date.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit' });
      case 'month':
        return date.toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' });
      default:
        return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    }
  }

  private draw(): void {
    const canvas = this.canvas()?.nativeElement;
    if (!canvas) return;
    this.chart?.destroy();
    const points = this.points();
    this.chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: points.map((p) => this.label(p.timestamp)),
        datasets: [
          {
            label: 'Énergie (kWh)',
            data: points.map((p) => p.energy_kwh),
            backgroundColor: 'rgba(16, 185, 129, 0.6)',
            borderRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 12, color: '#64748b' } },
          y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        },
      },
    });
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }
}
