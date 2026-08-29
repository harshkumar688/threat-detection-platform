import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { authService } from '../../services/authService';
import { UserRole } from '../../types/common';
import LoadingSpinner from './LoadingSpinner';

interface Props {
  children: React.ReactNode;
  requiredRole?: UserRole;
}

export default function ProtectedRoute({ children, requiredRole }: Props) {
  const { isAuthenticated, user, setUser, logout } = useAuthStore();
  const [loading, setLoading] = useState(!user && isAuthenticated);

  useEffect(() => {
    // If we have a token but no user info, fetch the profile
    if (isAuthenticated && !user) {
      authService.getMe()
        .then((userData) => {
          setUser(userData as any);
        })
        .catch(() => {
          // Token is invalid/expired — force logout
          logout();
        })
        .finally(() => setLoading(false));
    }
  }, [isAuthenticated, user]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (requiredRole && user) {
    const hierarchy: UserRole[] = ['admin', 'operator', 'viewer'];
    const userLevel = hierarchy.indexOf(user.role);
    const requiredLevel = hierarchy.indexOf(requiredRole);
    if (userLevel > requiredLevel) {
      return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-red-400">Access Denied</h2>
            <p className="text-gray-400 mt-2">You don't have permission to view this page.</p>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}
