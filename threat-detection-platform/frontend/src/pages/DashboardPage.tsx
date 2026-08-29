import { useEffect, useState } from 'react';
import { Camera, AlertTriangle, Shield, Activity } from 'lucide-react';
import StatCard from '../components/common/StatCard';
import SeverityBadge from '../components/common/SeverityBadge';
import { analyticsService } from '../services/analyticsService';
import { AnalyticsSummary } from '../types/analytics';

export default function DashboardPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    analyticsService.getSummary()
      .then(setSummary)
      .catch(() => {
        // API may return empty data — that's fine
        setSummary(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="animate-pulse text-gray-400">Loading dashboard...</div>;
  }

  const s = summary || { total_incidents: 0, open_incidents: 0, total_detections_today: 0, active_cameras: 0, incidents_by_severity: {} as Record<string, number>, avg_response_time_seconds: null as number | null };

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Cameras"
          value={s.active_cameras}
          icon={<Camera className="w-8 h-8" />}
          color="green"
          subtitle="Currently processing"
        />
        <StatCard
          title="Open Incidents"
          value={s.open_incidents}
          icon={<AlertTriangle className="w-8 h-8" />}
          color={s.open_incidents > 0 ? 'red' : 'gray'}
          subtitle="Requires attention"
        />
        <StatCard
          title="Critical Incidents"
          value={s.incidents_by_severity?.CRITICAL || 0}
          icon={<Shield className="w-8 h-8" />}
          color="red"
          subtitle="Maximum urgency"
        />
        <StatCard
          title="Today's Detections"
          value={s.total_detections_today}
          icon={<Activity className="w-8 h-8" />}
          color="blue"
          subtitle="Last 24 hours"
        />
      </div>

      {/* Severity Breakdown */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Incidents by Severity</h3>
        <div className="flex gap-4 flex-wrap">
          {Object.entries(s.incidents_by_severity).map(([level, count]) => (
            <div key={level} className="flex items-center gap-2">
              <SeverityBadge level={level} />
              <span className="text-white font-medium">{count as number}</span>
            </div>
          ))}
          {Object.keys(s.incidents_by_severity).length === 0 && (
            <p className="text-gray-500">No incidents recorded yet.</p>
          )}
        </div>
      </div>

      {/* System Status */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">System Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Total Incidents:</span>
            <span className="ml-2 text-white font-medium">{s.total_incidents}</span>
          </div>
          <div>
            <span className="text-gray-400">Response Time:</span>
            <span className="ml-2 text-white font-medium">
              {s.avg_response_time_seconds ? `${s.avg_response_time_seconds.toFixed(1)}s` : 'N/A'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
