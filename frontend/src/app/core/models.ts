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

export interface PeakPrediction {
  timestamp: string;
  predicted_kw: number;
  confidence: number;
}

export interface ConsumptionPoint {
  timestamp: string;
  consumption_kw: number;
}

export interface Recommendation {
  id: number;
  title: string;
  message: string;
  estimated_saving_kw: number | null;
}
