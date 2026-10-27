import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';

import { AlertsService } from '../../core/alerts.service';
import { Alert } from '../../core/models';
import { SiteSelect } from '../../shared/site-select/site-select';

type StatusFilter = 'active' | 'resolved' | 'all';

const STATUSES: { value: StatusFilter; label: string }[] = [
  { value: 'active', label: 'Actives' },
  { value: 'resolved', label: 'Résolues' },
  { value: 'all', label: 'Toutes' },
];

const SEVERITY_CLASSES: Record<string, string> = {
  critical: 'bg-red-700 text-white',
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-200 text-slate-700',
};

/** Alertes des sites, avec filtre par site et par état. */
@Component({
  selector: 'app-alerts',
  imports: [DatePipe, DecimalPipe, SiteSelect],
  templateUrl: './alerts.html',
})
export class Alerts implements OnInit {
  private readonly alertsService = inject(AlertsService);

  protected readonly statuses = STATUSES;
  protected readonly siteId = signal('');
  protected readonly status = signal<StatusFilter>('active');
  protected readonly alerts = signal<Alert[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  protected selectSite(siteId: string): void {
    this.siteId.set(siteId);
    this.load();
  }

  protected selectStatus(status: StatusFilter): void {
    this.status.set(status);
    this.load();
  }

  protected severityClass(severity: string): string {
    return SEVERITY_CLASSES[severity] ?? 'bg-slate-200 text-slate-700';
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.alertsService
      .getAlerts({ siteId: this.siteId() || undefined, status: this.status(), limit: 100 })
      .subscribe({
        next: (alerts) => {
          this.alerts.set(alerts);
          this.loading.set(false);
        },
        error: () => {
          this.error.set("Impossible de charger les alertes depuis l'API.");
          this.loading.set(false);
        },
      });
  }
}
