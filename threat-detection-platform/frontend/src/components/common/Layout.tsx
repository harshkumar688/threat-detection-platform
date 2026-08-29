import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { useAlertStore } from '../../store/alertStore';
import {
  LayoutDashboard, Video, AlertTriangle, Camera, BarChart3,
  Users, Settings, LogOut, Bell, Shield
} from 'lucide-react';
import clsx from 'clsx';

interface LayoutProps { children: ReactNode; }

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/monitoring', label: 'Live Monitoring', icon: Video },
  { path: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { path: '/cameras', label: 'Cameras', icon: Camera },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/users', label: 'Users', icon: Users, adminOnly: true },
  { path: '/settings', label: 'Settings', icon: Settings, adminOnly: true },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { unreadCount } = useAlertStore();

  const visibleNav = navItems.filter(
    (item) => !item.adminOnly || user?.role === 'admin'
  );

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-400" />
            <h1 className="text-lg font-bold text-blue-400">Threat Detection</h1>
          </div>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {visibleNav.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-700">
          <div className="text-sm text-gray-400 mb-2">
            {user?.full_name || 'User'}
            <span className="ml-2 px-2 py-0.5 bg-gray-700 rounded text-xs uppercase">
              {user?.role}
            </span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
          >
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 bg-gray-800 border-b border-gray-700 flex items-center justify-between px-6">
          <h2 className="text-lg font-semibold">
            {visibleNav.find((n) => n.path === location.pathname)?.label || 'Platform'}
          </h2>
          <div className="flex items-center gap-4">
            <Link to="/incidents?status=OPEN" className="relative">
              <Bell className="w-5 h-5 text-gray-400 hover:text-white" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </Link>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
