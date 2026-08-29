import api from './api';
import { LoginRequest, TokenResponse, User } from '../types/auth';

export const authService = {
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/auth/login', data);
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },

  refresh: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken });
    return res.data;
  },
};
