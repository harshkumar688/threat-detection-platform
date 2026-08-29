import api from './api';
import { User } from '../types/auth';

export const userService = {
  list: async (includeInactive = false): Promise<User[]> => {
    const res = await api.get<User[]>('/users/', { params: { include_inactive: includeInactive } });
    return res.data;
  },

  get: async (id: string): Promise<User> => {
    const res = await api.get<User>(`/users/${id}`);
    return res.data;
  },

  deactivate: async (id: string): Promise<User> => {
    const res = await api.put<User>(`/users/${id}/deactivate`);
    return res.data;
  },

  changeRole: async (id: string, role: string): Promise<User> => {
    const res = await api.put<User>(`/users/${id}/role`, { role });
    return res.data;
  },
};
