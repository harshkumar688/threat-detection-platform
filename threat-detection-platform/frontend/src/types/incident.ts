import { IncidentStatus, RiskLevel } from './common';

export interface Incident {
  id: string;
  incident_number: number;
  camera_id: string;
  threat_type: string;
  confidence: number;
  risk_score: number;
  risk_level: RiskLevel;
  status: IncidentStatus;
  track_id: number | null;
  location_id: string | null;
  location_name: string;
  building: string;
  zone: string;
  latitude: number | null;
  longitude: number | null;
  weapon_count: number;
  frames_confirmed: number;
  description: string;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentListItem {
  id: string;
  incident_number: number;
  camera_id: string;
  threat_type: string;
  risk_score: number;
  risk_level: RiskLevel;
  status: IncidentStatus;
  location_name: string;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
}
