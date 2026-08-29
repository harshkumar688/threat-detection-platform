import api from './api';
import { Camera, CameraCreateInput, CameraUpdateInput } from '../types/camera';

export const cameraService = {
  list: async (): Promise<Camera[]> => {
    const res = await api.get<Camera[]>('/cameras/');
    return res.data;
  },

  get: async (id: string): Promise<Camera> => {
    const res = await api.get<Camera>(`/cameras/${id}`);
    return res.data;
  },

  create: async (data: CameraCreateInput): Promise<Camera> => {
    const res = await api.post<Camera>('/cameras/', data);
    return res.data;
  },

  update: async (id: string, data: CameraUpdateInput): Promise<Camera> => {
    const res = await api.put<Camera>(`/cameras/${id}`, data);
    return res.data;
  },

  start: async (id: string) => {
    const res = await api.post(`/cameras/${id}/start`);
    return res.data;
  },

  stop: async (id: string) => {
    const res = await api.post(`/cameras/${id}/stop`);
    return res.data;
  },

  delete: async (id: string) => {
    await api.delete(`/cameras/${id}`);
  },
};
