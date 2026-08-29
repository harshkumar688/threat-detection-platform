import api from './api';
import { Alert, AlertCounts } from '../types/alert';
import { PaginatedResponse } from '../types/common';

export const alertService = {
  list: async (params?: { page?: number; severity?: string; acknowledged?: boolean }) => {
    const res = await api.get<PaginatedResponse<Alert>>('/alerts/', { params });
    return res.data;
  },

  getCounts: async (): Promise<AlertCounts> => {
    const res = await api.get<AlertCounts>('/alerts/count');
    return res.data;
  },

  acknowledge: async (id: string, notes?: string) => {
    const res = await api.put(`/alerts/${id}/acknowledge`, { notes });
    return res.data;
  },
};
