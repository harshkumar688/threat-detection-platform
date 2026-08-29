import { create } from 'zustand';
import { UserRole } from '../types/common';

interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  login: (accessToken: string, refreshToken: string, user: UserInfo | null) => void;
  logout: () => void;
  setUser: (user: UserInfo) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: (accessToken, refreshToken, user) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    set({ user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
    window.location.href = '/login';
  },

  setUser: (user) => set({ user, isAuthenticated: true }),
}));
