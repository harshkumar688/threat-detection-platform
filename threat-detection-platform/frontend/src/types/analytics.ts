export interface AnalyticsSummary {
  total_incidents: number;
  open_incidents: number;
  total_detections_today: number;
  active_cameras: number;
  avg_response_time_seconds: number | null;
  incidents_by_severity: Record<string, number>;
}

export interface TimelinePoint {
  timestamp: string;
  count: number;
  label: string;
}

export interface DistributionItem {
  name: string;
  count: number;
  percentage: number;
}
