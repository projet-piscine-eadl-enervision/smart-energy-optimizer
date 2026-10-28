/**
 * Types des données échangées avec l'API.
 * Ils reprennent les schémas Pydantic de api/app/schemas/ — à garder synchronisés.
 */

export type Role = 'user' | 'admin';

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  role: Role;
  /** Site de rattachement : un `user` ne voit que celui-ci, un `admin` voit tous les sites. */
  site_id: string | null;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

/** Prévision d'une heure, pour un site ou pour le total des sites (site_id = "ALL"). */
export interface Prediction {
  timestamp: string;
  predicted_kw: number;
  site_id: string;
  /** Vide pour le total des sites : un pic est propre à chaque site. */
  is_peak: boolean | null;
  model_version: string;
  /** Aucune incertitude n'est produite pour l'instant. */
  confidence?: number | null;
}

/** Heure annoncée en pic pour un site, avec le seuil du site. */
export interface PeakHour {
  timestamp: string;
  site_id: string;
  predicted_kw: number;
  threshold_kw: number | null;
  excess_kw: number | null;
  model_version: string;
}

export interface ConsumptionPoint {
  timestamp: string;
  consumption_kw: number;
}

export interface Recommendation {
  id: number;
  title: string;
  message: string;
  /** Part décalable du dépassement prévu ; vide pour une alerte. */
  estimated_saving_kw: number | null;
  site_id: string;
  target_time: string;
  alert_type: string;
}

export type AlertStatus = 'active' | 'resolved';

/** Alerte d'un site ; received_at est le dernier tour de collecte où elle a été vue. */
export interface Alert {
  alert_id: string;
  timestamp: string;
  received_at: string;
  site_id: string;
  site_name: string;
  severity: string;
  alert_type: string;
  alert_label: string;
  message: string | null;
  value: number | null;
  threshold: number | null;
  origin: 'api' | 'rule';
  status: AlertStatus;
}

/** Site avec sa dernière consommation connue (non nulle) et la qualité du dernier relevé. */
export interface Site {
  site_id: string;
  site_name: string;
  site_type: string;
  location: string | null;
  capacity_kw: number;
  status: string;
  last_consumption_kw: number | null;
  last_reading_age_minutes: number | null;
  last_quality: string | null;
}

export type Period = 'hour' | 'day' | 'week' | 'month';

/** Consommation d'une période : énergie (kWh) et pointe (kW). */
export interface SiteConsumptionPoint {
  timestamp: string;
  energy_kwh: number;
  max_kw: number | null;
}

export interface SiteQuality {
  site_id: string;
  days: number;
  readings: number;
  missing_ratio: number | null;
  by_quality: Record<string, number>;
  sensor_outages: number;
}
