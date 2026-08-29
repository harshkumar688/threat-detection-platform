import api from './api';
import { PaginatedResponse } from '../types/common';
import { Incident, IncidentListItem } from '../types/incident';

export const incidentService = {
  list: async (params?: { page?: number; page_size?: number; status?: string; camera_id?: string; risk_level?: string }) => {
    const res = await api.get<PaginatedResponse<IncidentListItem>>('/incidents/', { params });
    return res.data;
  },

  get: async (id: string): Promise<Incident> => {
    const res = await api.get<Incident>(`/incidents/${id}`);
    return res.data;
  },

  updateStatus: async (id: string, status: string, notes?: string) => {
    const res = await api.put(`/incidents/${id}/status`, { status, notes });
    return res.data;
  },

  create: async (data: { camera_id: string; threat_type: string; description?: string; risk_level?: string }) => {
    const res = await api.post('/incidents/', data);
    return res.data;
  },
};
