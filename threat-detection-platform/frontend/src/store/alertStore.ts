import { create } from 'zustand';
import { Alert } from '../types/alert';

interface AlertState {
  alerts: Alert[];
  unreadCount: number;
  addAlert: (alert: Alert) => void;
  setAlerts: (alerts: Alert[]) => void;
  setUnreadCount: (count: number) => void;
  markRead: (id: string) => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  unreadCount: 0,

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50),
      unreadCount: state.unreadCount + 1,
    })),

  setAlerts: (alerts) => set({ alerts }),
  setUnreadCount: (count) => set({ unreadCount: count }),

  markRead: (id) =>
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, is_read: true } : a)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    })),
}));
