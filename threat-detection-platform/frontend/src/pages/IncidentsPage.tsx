import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { incidentService } from '../services/incidentService';
import { IncidentListItem } from '../types/incident';
import { PaginationMeta } from '../types/common';
import SeverityBadge from '../components/common/SeverityBadge';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { formatDistanceToNow } from 'date-fns';

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([]);
  const [meta, setMeta] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    incidentService
      .list({ page, page_size: 20, status: statusFilter || undefined })
      .then((res) => {
        setIncidents(res.data);
        setMeta(res.meta);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-3 items-center">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
        >
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="RESOLVED">Resolved</option>
          <option value="FALSE_POSITIVE">False Positive</option>
        </select>
        {meta && <span className="text-sm text-gray-400">{meta.total_items} total</span>}
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-750 border-b border-gray-700">
              <tr className="text-gray-400 text-left">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Threat</th>
                <th className="px-4 py-3">Camera</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id} className="border-b border-gray-700 hover:bg-gray-750 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/incidents/${inc.id}`} className="text-blue-400 hover:underline">
                      #{inc.incident_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium capitalize">{inc.threat_type}</td>
                  <td className="px-4 py-3 text-gray-400">{inc.camera_id}</td>
                  <td className="px-4 py-3 text-gray-400">{inc.location_name || '—'}</td>
                  <td className="px-4 py-3">
                    <SeverityBadge level={inc.risk_level} />
                    <span className="ml-2 text-xs text-gray-500">{inc.risk_score.toFixed(0)}</span>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={inc.status} /></td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {formatDistanceToNow(new Date(inc.created_at), { addSuffix: true })}
                  </td>
                </tr>
              ))}
              {incidents.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    No incidents found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-400">
                Page {meta.page} of {meta.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
                disabled={page === meta.total_pages}
                className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
