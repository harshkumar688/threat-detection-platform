import api from './api';
import { AnalyticsSummary, TimelinePoint, DistributionItem } from '../types/analytics';

interface TimelineResponse {
  data: TimelinePoint[];
  granularity: string;
  total: number;
}

interface DistributionResponse {
  data: DistributionItem[];
  total: number;
  group_by: string;
}

interface FalsePositiveRate {
  rate: number | null;
  false_positives: number;
  true_positives: number;
  total_labeled: number;
  note: string;
}

export const analyticsService = {
  getSummary: async (): Promise<AnalyticsSummary> => {
    const res = await api.get<AnalyticsSummary>('/analytics/summary');
    return res.data;
  },

  getIncidentsTimeline: async (granularity = 'daily', days = 7): Promise<TimelineResponse> => {
    const res = await api.get<TimelineResponse>('/analytics/incidents/timeline', { params: { granularity, days } });
    return res.data;
  },

  getDetectionsTimeline: async (granularity = 'daily', days = 7): Promise<TimelineResponse> => {
    const res = await api.get<TimelineResponse>('/analytics/detections/timeline', { params: { granularity, days } });
    return res.data;
  },

  getByCamera: async (): Promise<DistributionResponse> => {
    const res = await api.get<DistributionResponse>('/analytics/incidents/by-camera');
    return res.data;
  },

  getBySeverity: async (): Promise<DistributionResponse> => {
    const res = await api.get<DistributionResponse>('/analytics/incidents/by-severity');
    return res.data;
  },

  getByWeapon: async (): Promise<DistributionResponse> => {
    const res = await api.get<DistributionResponse>('/analytics/incidents/by-weapon');
    return res.data;
  },

  getByHour: async (days = 7): Promise<TimelineResponse> => {
    const res = await api.get<TimelineResponse>('/analytics/incidents/by-hour', { params: { days } });
    return res.data;
  },

  getByStatus: async (): Promise<DistributionResponse> => {
    const res = await api.get<DistributionResponse>('/analytics/incidents/by-status');
    return res.data;
  },

  getFalsePositiveRate: async (): Promise<FalsePositiveRate> => {
    const res = await api.get<FalsePositiveRate>('/analytics/false-positive-rate');
    return res.data;
  },
};
