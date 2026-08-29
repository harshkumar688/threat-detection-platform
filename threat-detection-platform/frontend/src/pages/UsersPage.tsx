import { useEffect, useState } from 'react';
import { UserX, ShieldCheck } from 'lucide-react';
import { userService } from '../services/userService';
import { User } from '../types/auth';
import { useAuthStore } from '../store/authStore';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { format } from 'date-fns';

const ROLES = ['admin', 'operator', 'viewer'];

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { user: currentUser } = useAuthStore();

  const load = () => {
    setLoading(true);
    userService
      .list()
      .then(setUsers)
      .catch(() => setError('Failed to load users.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleDeactivate = async (id: string) => {
    try {
      await userService.deactivate(id);
      load();
    } catch {
      setError('Failed to deactivate user.');
    }
  };

  const handleRoleChange = async (id: string, role: string) => {
    try {
      await userService.changeRole(id, role);
      load();
    } catch {
      setError('Failed to change role.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">User Management</h2>
        <span className="text-sm text-gray-400">{users.length} active user{users.length !== 1 ? 's' : ''}</span>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-left border-b border-gray-700">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Login</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-gray-700 last:border-0">
                  <td className="px-4 py-3">{u.full_name}</td>
                  <td className="px-4 py-3 text-gray-400">{u.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      disabled={u.id === currentUser?.id}
                      className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs disabled:opacity-50"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r.toUpperCase()}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${u.is_active ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/20 text-gray-400'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {u.last_login_at ? format(new Date(u.last_login_at), 'PPp') : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active && u.id !== currentUser?.id && (
                      <button
                        onClick={() => handleDeactivate(u.id)}
                        className="flex items-center gap-1 px-2 py-1 bg-red-600/20 text-red-400 rounded text-xs hover:bg-red-600/30"
                      >
                        <UserX className="w-3 h-3" /> Deactivate
                      </button>
                    )}
                    {u.id === currentUser?.id && (
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <ShieldCheck className="w-3 h-3" /> You
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
