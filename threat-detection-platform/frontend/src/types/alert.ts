import { Severity } from './common';

export interface Alert {
  id: string;
  incident_id: string;
  camera_id: string;
  severity: Severity;
  title: string;
  message: string;
  alert_type: string;
  is_read: boolean;
  is_acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  created_at: string;
}

export interface AlertCounts {
  total_unread: number;
  total_unacknowledged: number;
  by_severity: Record<string, number>;
}
