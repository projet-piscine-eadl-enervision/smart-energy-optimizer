import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, ElementRef, inject, OnDestroy, OnInit, signal, viewChild } from '@angular/core';
import { forkJoin } from 'rxjs';
import { Chart, registerables } from 'chart.js';

import { EnergyService } from '../../core/energy.service';
import { ConsumptionPoint, Prediction, Recommendation } from '../../core/models';
import { SiteSelect } from '../../shared/site-select/site-select';

Chart.register(...registerables);

const PERIODS = [
  { days: 1, label: '24 h' },
  { days: 7, label: '7 jours' },
  { days: 30, label: '30 jours' },
] as const;

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, DecimalPipe, SiteSelect],
  templateUrl: './dashboard.html',
})
export class Dashboard implements OnInit, OnDestroy {
  private readonly energy = inject(EnergyService);

  private readonly historyCanvas = viewChild<ElementRef<HTMLCanvasElement>>('historyChart');
  private readonly predictionsCanvas = viewChild<ElementRef<HTMLCanvasElement>>('predictionsChart');
  private historyChart: Chart | null = null;
  private predictionsChart: Chart | null = null;

  protected readonly periods = PERIODS;
  protected readonly siteId = signal('');
  protected readonly days = signal<number>(1);
  protected readonly predictions = signal<Prediction[]>([]);
  protected readonly history = signal<ConsumptionPoint[]>([]);
  protected readonly recommendations = signal<Recommendation[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  protected selectSite(siteId: string): void {
    this.siteId.set(siteId);
    this.load();
  }

  protected selectPeriod(days: number): void {
    this.days.set(days);
    this.load();
  }

  protected periodLabel(): string {
    return PERIODS.find((p) => p.days === this.days())?.label ?? '';
  }

  private load(): void {
    const site = this.siteId() || undefined;
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      predictions: this.energy.getPredictions(24, site),
      history: this.energy.getHistory(this.days(), site),
      recommendations: this.energy.getRecommendations(24, site),
    }).subscribe({
      next: (data) => {
        this.predictions.set(data.predictions);
        this.history.set(data.history);
        this.recommendations.set(data.recommendations);
        this.loading.set(false);
        // Les canvas n'existent qu'après le rendu des sections
        setTimeout(() => this.drawCharts(), 0);
      },
      error: () => {
        this.error.set("Impossible de charger les données depuis l'API.");
        this.loading.set(false);
      },
    });
  }

  private drawCharts(): void {
    const history = this.historyCanvas()?.nativeElement;
    if (history) this.drawHistory(history, this.history());
    const predictions = this.predictionsCanvas()?.nativeElement;
    if (predictions) this.drawPredictions(predictions, this.predictions());
  }

  private label(timestamp: string): string {
    const date = new Date(timestamp);
    return this.days() > 1
      ? date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit' })
      : date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  private drawHistory(canvas: HTMLCanvasElement, data: ConsumptionPoint[]): void {
    this.historyChart?.destroy();
    // L'API renvoie les points du plus récent au plus ancien
    const points = [...data].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    this.historyChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: points.map((p) => this.label(p.timestamp)),
        datasets: [
          {
            label: 'Consommation (kW)',
            data: points.map((p) => p.consumption_kw),
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            pointHitRadius: 10,
            borderWidth: 2,
          },
        ],
      },
      options: this.options(),
    });
  }

  private drawPredictions(canvas: HTMLCanvasElement, data: Prediction[]): void {
    this.predictionsChart?.destroy();
    this.predictionsChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.map((p) => this.label(p.timestamp)),
        datasets: [
          {
            label: 'Puissance prévue (kW)',
            data: data.map((p) => p.predicted_kw),
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            borderDash: [6, 4],
            // Un pic est en rouge et plus gros
            pointBackgroundColor: data.map((p) => (p.is_peak ? '#dc2626' : '#f59e0b')),
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: data.map((p) => (p.is_peak ? 7 : 4)),
            pointHoverRadius: 8,
          },
        ],
      },
      options: this.options((i) => (data[i].is_peak ? 'Pic prévu' : '')),
    });
  }

  private options(afterLabel?: (index: number) => string) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: 'index' as const,
          intersect: false,
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          padding: 10,
          callbacks: afterLabel
            ? { afterLabel: (c: { dataIndex: number }) => afterLabel(c.dataIndex) }
            : {},
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 8, color: '#64748b' } },
        y: {
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: { color: '#64748b' },
          border: { display: false },
        },
      },
      interaction: { mode: 'nearest' as const, axis: 'x' as const, intersect: false },
    };
  }

  ngOnDestroy(): void {
    this.historyChart?.destroy();
    this.predictionsChart?.destroy();
  }
}
