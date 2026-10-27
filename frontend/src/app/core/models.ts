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
