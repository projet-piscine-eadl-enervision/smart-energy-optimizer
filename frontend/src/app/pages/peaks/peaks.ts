import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnergyService } from '../../core/energy.service';
import { PeakHour } from '../../core/models';
import { SitesService } from '../../core/sites.service';
import { SiteSelect } from '../../shared/site-select/site-select';

const HORIZONS = [24, 48, 72] as const;
const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

/** Un pic enrichi pour l'affichage : nom du site, dépassement relatif et gravité. */
interface PeakRow {
  peak: PeakHour;
  siteName: string | null;
  /** Dépassement en % du seuil ; vide quand le seuil est inconnu. */
  percent: number | null;
  badge: string;
  bar: string;
  /** Largeur de la barre, en % de la ligne. */
  width: number;
}

interface DayGroup {
  label: string;
  rows: PeakRow[];
}

interface SiteStrip {
  siteId: string;
  siteName: string | null;
  /** Une case par heure à partir de l'heure en cours : le pic prévu à cette heure, ou rien. */
  cells: (PeakRow | null)[];
}

/** Gravité selon le dépassement du seuil : léger sous 10 %, marqué sous 25 %, fort au-delà. */
function severity(percent: number | null): Pick<PeakRow, 'badge' | 'bar'> {
  if (percent === null) return { badge: 'bg-slate-100 text-slate-600', bar: 'bg-slate-300' };
  if (percent < 10) return { badge: 'bg-amber-100 text-amber-800', bar: 'bg-amber-400' };
  if (percent < 25) return { badge: 'bg-orange-100 text-orange-800', bar: 'bg-orange-500' };
  return { badge: 'bg-red-100 text-red-700', bar: 'bg-red-600' };
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Heures où la consommation prévue d'un site dépasse son seuil habituel (pic), par jour et par site. */
@Component({
  selector: 'app-peaks',
  imports: [DatePipe, DecimalPipe, RouterLink, SiteSelect],
  templateUrl: './peaks.html',
})
export class Peaks implements OnInit {
  private readonly energy = inject(EnergyService);
  private readonly sitesService = inject(SitesService);

  protected readonly horizons = HORIZONS;
  protected readonly siteId = signal('');
  protected readonly hours = signal<number>(24);
  protected readonly peaks = signal<PeakHour[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  /** Début de la fenêtre affichée : l'heure en cours au moment du chargement. */
  private readonly from = signal(Math.floor(Date.now() / HOUR_MS) * HOUR_MS);

  protected readonly rows = computed<PeakRow[]>(() => {
    const names = new Map(this.sitesService.sites().map((s) => [s.site_id, s.site_name]));
    return this.peaks().map((peak) => {
      const percent =
        peak.excess_kw !== null && peak.threshold_kw ? (peak.excess_kw / peak.threshold_kw) * 100 : null;
      return {
        peak,
        siteName: names.get(peak.site_id) ?? null,
        percent,
        ...severity(percent),
        width: percent === null ? 0 : Math.min(100, Math.max(8, percent * 3)),
      };
    });
  });

  protected readonly days = computed<DayGroup[]>(() => {
    const today = startOfDay(new Date(this.from()));
    const groups = new Map<number, PeakRow[]>();
    for (const row of this.rows()) {
      const day = startOfDay(new Date(row.peak.timestamp));
      groups.set(day, [...(groups.get(day) ?? []), row]);
    }
    return [...groups.entries()]
      .sort(([a], [b]) => a - b)
      .map(([day, rows]) => ({ label: this.dayLabel(day, today), rows }));
  });

  protected readonly siteCount = computed(() => new Set(this.peaks().map((p) => p.site_id)).size);

  /** Le pic le plus marqué, au dépassement relatif le plus grand. */
  protected readonly strongest = computed(() =>
    this.rows().reduce<PeakRow | null>(
      (best, row) => (row.percent !== null && (best === null || row.percent > best.percent!) ? row : best),
      null,
    ),
  );

  protected readonly strips = computed<SiteStrip[]>(() => {
    const bySite = new Map<string, SiteStrip>();
    for (const row of this.rows()) {
      const strip = bySite.get(row.peak.site_id) ?? {
        siteId: row.peak.site_id,
        siteName: row.siteName,
        cells: Array<PeakRow | null>(this.hours()).fill(null),
      };
      const index = Math.floor((new Date(row.peak.timestamp).getTime() - this.from()) / HOUR_MS);
      if (index >= 0 && index < strip.cells.length) strip.cells[index] = row;
      bySite.set(row.peak.site_id, strip);
    }
    return [...bySite.values()].sort((a, b) => a.siteId.localeCompare(b.siteId));
  });

  /** Repères de la frise : une heure sur six, positionnée en % de la largeur. */
  protected readonly ticks = computed(() =>
    Array.from({ length: Math.ceil(this.hours() / 6) }, (_, i) => {
      const date = new Date(this.from() + i * 6 * HOUR_MS);
      return {
        left: ((i * 6) / this.hours()) * 100,
        label: `${String(date.getHours()).padStart(2, '0')} h`,
      };
    }),
  );

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

  protected cellTitle(row: PeakRow): string {
    const date = new Date(row.peak.timestamp);
    const hour = `${String(date.getHours()).padStart(2, '0')} h`;
    const percent = row.percent === null ? '' : ` (+${Math.round(row.percent)} %)`;
    return `${hour} : ${row.peak.predicted_kw.toFixed(1)} kW prévus${percent}`;
  }

  private dayLabel(day: number, today: number): string {
    const gap = Math.round((day - today) / DAY_MS);
    const date = new Date(day).toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: '2-digit' });
    if (gap === 0) return `Aujourd'hui, ${date}`;
    if (gap === 1) return `Demain, ${date}`;
    return date.charAt(0).toUpperCase() + date.slice(1);
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.energy.getPeaks(this.hours(), this.siteId() || undefined).subscribe({
      next: (peaks) => {
        this.from.set(Math.floor(Date.now() / HOUR_MS) * HOUR_MS);
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
