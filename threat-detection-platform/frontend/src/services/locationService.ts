import api from './api';
import { Location, LocationCreateInput, LocationUpdateInput } from '../types/location';

export const locationService = {
  list: async (isActive?: boolean): Promise<Location[]> => {
    const res = await api.get<Location[]>('/locations/', {
      params: isActive === undefined ? undefined : { is_active: isActive },
    });
    return res.data;
  },

  get: async (id: string): Promise<Location> => {
    const res = await api.get<Location>(`/locations/${id}`);
    return res.data;
  },

  create: async (data: LocationCreateInput): Promise<Location> => {
    const res = await api.post<Location>('/locations/', data);
    return res.data;
  },

  update: async (id: string, data: LocationUpdateInput): Promise<Location> => {
    const res = await api.put<Location>(`/locations/${id}`, data);
    return res.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/locations/${id}`);
  },
};
