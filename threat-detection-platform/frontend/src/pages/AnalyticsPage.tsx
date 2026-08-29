import { useEffect, useState } from 'react';
import { analyticsService } from '../services/analyticsService';
import { AnalyticsSummary, TimelinePoint, DistributionItem } from '../types/analytics';
import StatCard from '../components/common/StatCard';
import SeverityBadge from '../components/common/SeverityBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { BarChart3, TrendingUp, AlertTriangle, Clock } from 'lucide-react';

interface FPRate {
  rate: number | null;
  false_positives: number;
  true_positives: number;
  total_labeled: number;
  note: string;
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [bySeverity, setBySeverity] = useState<DistributionItem[]>([]);
  const [byWeapon, setByWeapon] = useState<DistributionItem[]>([]);
  const [byCamera, setByCamera] = useState<DistributionItem[]>([]);
  const [byHour, setByHour] = useState<TimelinePoint[]>([]);
  const [byStatus, setByStatus] = useState<DistributionItem[]>([]);
  const [fpRate, setFpRate] = useState<FPRate | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      analyticsService.getSummary().then(setSummary).catch(() => null),
      analyticsService.getIncidentsTimeline('daily', 7).then((r) => setTimeline(r.data)).catch(() => null),
      analyticsService.getBySeverity().then((r) => setBySeverity(r.data)).catch(() => null),
      analyticsService.getByWeapon().then((r) => setByWeapon(r.data)).catch(() => null),
      analyticsService.getByCamera().then((r) => setByCamera(r.data)).catch(() => null),
      analyticsService.getByHour().then((r) => setByHour(r.data)).catch(() => null),
      analyticsService.getByStatus().then((r) => setByStatus(r.data)).catch(() => null),
      analyticsService.getFalsePositiveRate().then(setFpRate).catch(() => null),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Total Incidents" value={summary?.total_incidents || 0} icon={<AlertTriangle className="w-8 h-8" />} color="blue" />
        <StatCard title="Open Incidents" value={summary?.open_incidents || 0} icon={<BarChart3 className="w-8 h-8" />} color={summary?.open_incidents ? 'red' : 'gray'} />
        <StatCard title="Today's Detections" value={summary?.total_detections_today || 0} icon={<TrendingUp className="w-8 h-8" />} color="green" />
        <StatCard
          title="False Positive Rate"
          value={fpRate && fpRate.rate !== null ? `${fpRate.rate}%` : 'N/A'}
          icon={<Clock className="w-8 h-8" />}
          color="yellow"
          subtitle={fpRate?.note || ''}
        />
      </div>

      {/* Row 1: Timeline + Hourly Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incidents Over Time */}
        <ChartCard title="Incidents Over Time (7 days)">
          {timeline.length > 0 ? (
            <BarChartSimple data={timeline} color="bg-blue-500" />
          ) : (
            <EmptyChart message="No incident data yet. Create incidents to see trends." />
          )}
        </ChartCard>

        {/* Hour-wise Trends */}
        <ChartCard title="Hour-of-Day Activity">
          {byHour.some((p) => p.count > 0) ? (
            <BarChartSimple data={byHour} color="bg-purple-500" />
          ) : (
            <EmptyChart message="No data. Trends appear as incidents accumulate." />
          )}
        </ChartCard>
      </div>

      {/* Row 2: Distributions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Risk Level */}
        <ChartCard title="Risk Level Distribution">
          {bySeverity.length > 0 ? (
            <DistributionList data={bySeverity} type="severity" />
          ) : (
            <EmptyChart message="No data." />
          )}
        </ChartCard>

        {/* Weapon Categories */}
        <ChartCard title="Weapon Categories">
          {byWeapon.length > 0 ? (
            <DistributionList data={byWeapon} type="default" />
          ) : (
            <EmptyChart message="No data." />
          )}
        </ChartCard>

        {/* Camera Distribution */}
        <ChartCard title="Incidents by Camera">
          {byCamera.length > 0 ? (
            <DistributionList data={byCamera} type="default" />
          ) : (
            <EmptyChart message="No data." />
          )}
        </ChartCard>
      </div>

      {/* Row 3: Resolution Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Resolution Status">
          {byStatus.length > 0 ? (
            <DistributionList data={byStatus} type="status" />
          ) : (
            <EmptyChart message="No resolved incidents yet." />
          )}
        </ChartCard>

        {/* False Positive Analysis */}
        <ChartCard title="Detection Accuracy">
          {fpRate ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div className="p-4 bg-green-500/10 rounded-lg border border-green-500/30">
                  <p className="text-2xl font-bold text-green-400">{fpRate.true_positives}</p>
                  <p className="text-sm text-gray-400">True Positives</p>
                </div>
                <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/30">
                  <p className="text-2xl font-bold text-red-400">{fpRate.false_positives}</p>
                  <p className="text-sm text-gray-400">False Positives</p>
                </div>
              </div>
              <p className="text-sm text-gray-400 text-center">{fpRate.note}</p>
              {fpRate.rate !== null && (
                <div className="text-center">
                  <p className="text-3xl font-bold text-yellow-400">{fpRate.rate}%</p>
                  <p className="text-sm text-gray-400">False Positive Rate</p>
                </div>
              )}
            </div>
          ) : (
            <EmptyChart message="Accuracy data not available." />
          )}
        </ChartCard>
      </div>
    </div>
  );
}

// ─── Reusable Sub-Components ─────────────────────────────────────────────────

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      {children}
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return <p className="text-gray-500 text-sm text-center py-8">{message}</p>;
}

function BarChartSimple({ data, color }: { data: TimelinePoint[]; color: string }) {
  const maxCount = Math.max(...data.map((p) => p.count), 1);
  return (
    <div className="h-48 flex items-end gap-1">
      {data.map((point, i) => (
        <div key={i} className="flex-1 flex flex-col items-center">
          <div
            className={`w-full ${color} rounded-t transition-all`}
            style={{ height: `${Math.max(2, (point.count / maxCount) * 160)}px` }}
            title={`${point.label}: ${point.count}`}
          />
          <span className="text-xs text-gray-500 mt-1 truncate w-full text-center">
            {point.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function DistributionList({ data, type }: { data: DistributionItem[]; type: string }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.name} className="flex items-center gap-3">
          <span className="w-24 text-sm text-gray-400 truncate">
            {type === 'severity' ? <SeverityBadge level={item.name} /> : item.name}
          </span>
          <div className="flex-1 bg-gray-700 rounded-full h-3">
            <div
              className="bg-blue-500 rounded-full h-3 transition-all"
              style={{ width: `${(item.count / maxCount) * 100}%` }}
            />
          </div>
          <span className="text-sm font-medium w-10 text-right">{item.count}</span>
          <span className="text-xs text-gray-500 w-12 text-right">{item.percentage}%</span>
        </div>
      ))}
    </div>
  );
}
