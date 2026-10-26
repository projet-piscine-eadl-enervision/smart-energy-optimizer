import { DecimalPipe } from '@angular/common';
import { Component, inject, OnInit, signal, viewChild, ElementRef, OnDestroy } from '@angular/core';
import { forkJoin } from 'rxjs';
import { Chart, registerables } from 'chart.js';

import { AuthService } from '../../core/auth.service';
import { EnergyService } from '../../core/energy.service';
import { ConsumptionPoint, PeakPrediction, Recommendation, User } from '../../core/models';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  imports: [DecimalPipe],
  templateUrl: './dashboard.html',
})
export class Dashboard implements OnInit, OnDestroy {
  protected readonly auth = inject(AuthService);
  private readonly energy = inject(EnergyService);

  // Références vers les trois Canvas
  historyChartRef = viewChild<ElementRef<HTMLCanvasElement>>('historyChart');
  predictionsLineChartRef = viewChild<ElementRef<HTMLCanvasElement>>('predictionsLineChart');

  // Stockage des trois instances de graphiques distinctes
  private historyChartInstance: Chart | null = null;
  private predictionsChartInstance: Chart | null = null;
  private predictionsLineChartInstance: Chart | null = null;

  protected readonly user = signal<User | null>(null);
  protected readonly predictions = signal<PeakPrediction[]>([]);
  protected readonly history = signal<ConsumptionPoint[]>([]);
  protected readonly recommendations = signal<Recommendation[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  constructor() {}

  ngOnInit(): void {
    forkJoin({
      user: this.auth.me(),
      predictions: this.energy.getPredictions(),
      history: this.energy.getHistory(1),
      recommendations: this.energy.getRecommendations(),
    }).subscribe({
      next: (data) => {
        this.user.set(data.user);
        this.predictions.set(data.predictions);
        this.history.set(data.history);
        this.recommendations.set(data.recommendations);

        this.loading.set(false);

        // Génération des trois graphiques
        setTimeout(() => {
          const histCanvas = this.historyChartRef()?.nativeElement;
          if (histCanvas) {
            this.renderAreaChart(histCanvas, data.history);
          }

          const predLineCanvas = this.predictionsLineChartRef()?.nativeElement;
          if (predLineCanvas) {
            this.renderPredictionLineChart(predLineCanvas, data.predictions);
          }
        }, 100);
      },
      error: () => {
        this.error.set("Impossible de charger les données depuis l'API.");
        this.loading.set(false);
      },
    });
  }

  // --- Graphique Historique (Zone/Ligne) ---
  private renderAreaChart(canvas: HTMLCanvasElement, data: ConsumptionPoint[]): void {
    if (this.historyChartInstance) {
      this.historyChartInstance.destroy();
    }

    const chronologicalData = [...data].reverse();

    this.historyChartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels: chronologicalData.map((d) => {
          const date = new Date(d.timestamp);
          return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        }),
        datasets: [{
          label: 'Consommation (kW)',
          data: chronologicalData.map((d) => d.consumption_kw),
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.15)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHitRadius: 10,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { mode: 'index', intersect: false, backgroundColor: 'rgba(15, 23, 42, 0.9)', padding: 10 },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 8, color: '#64748b' } },
          y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' }, border: { display: false } },
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
      },
    });
  }

  // --- Graphique Prédictions (Courbe Modifiée - Pointillés) ---
  private renderPredictionLineChart(canvas: HTMLCanvasElement, data: PeakPrediction[]): void {
    if (this.predictionsLineChartInstance) {
      this.predictionsLineChartInstance.destroy();
    }

    this.predictionsLineChartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.map((d) => {
          const date = new Date(d.timestamp);
          return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        }),
        datasets: [{
          label: 'Puissance prévue (kW)',
          data: data.map((d) => d.predicted_kw),
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.1)',
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          borderDash: [6, 4],
          pointBackgroundColor: data.map((d) => `rgba(245, 158, 11, ${d.confidence})`),
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            padding: 10,
            callbacks: {
              afterLabel: (context) => {
                const confidenceRaw = data[context.dataIndex].confidence;
                const confidencePct = confidenceRaw <= 1 ? confidenceRaw * 100 : confidenceRaw;
                return `Confiance : ${confidencePct.toFixed(0)}%`;
              }
            }
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#64748b' } },
          y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' }, border: { display: false } },
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
      },
    });
  }

  ngOnDestroy(): void {
    if (this.historyChartInstance) {
      this.historyChartInstance.destroy();
    }
    if (this.predictionsChartInstance) {
      this.predictionsChartInstance.destroy();
    }
    if (this.predictionsLineChartInstance) {
      this.predictionsLineChartInstance.destroy();
    }
  }
}
