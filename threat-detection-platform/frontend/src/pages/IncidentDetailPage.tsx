import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { incidentService } from '../services/incidentService';
import { Incident } from '../types/incident';
import SeverityBadge from '../components/common/SeverityBadge';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import EvidenceViewer from '../components/incidents/EvidenceViewer';
import { useAuthStore } from '../store/authStore';
import { format } from 'date-fns';

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!id) return;
    incidentService.get(id).then(setIncident).catch(() => navigate('/incidents')).finally(() => setLoading(false));
  }, [id]);

  const handleStatusUpdate = async (newStatus: string) => {
    if (!id || !incident) return;
    setUpdating(true);
    try {
      const updated = await incidentService.updateStatus(id, newStatus);
      setIncident(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!incident) return <p className="text-red-400">Incident not found.</p>;

  const canModify = user?.role === 'admin' || user?.role === 'operator';

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Incident #{incident.incident_number}</h2>
          <p className="text-gray-400 mt-1">{incident.description}</p>
        </div>
        <div className="flex items-center gap-3">
          <SeverityBadge level={incident.risk_level} size="md" />
          <StatusBadge status={incident.status} size="md" />
        </div>
      </div>

      {/* Details Grid */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Details</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <Field label="Threat Type" value={incident.threat_type} />
          <Field label="Camera" value={incident.camera_id} />
          <Field label="Location" value={incident.location_name || '—'} />
          <Field label="Building / Zone" value={[incident.building, incident.zone].filter(Boolean).join(' / ') || '—'} />
          <Field
            label="Coordinates"
            value={
              incident.latitude != null && incident.longitude != null
                ? `${incident.latitude.toFixed(4)}, ${incident.longitude.toFixed(4)}`
                : '—'
            }
          />
          <Field label="Risk Score" value={`${incident.risk_score.toFixed(1)} / 100`} />
          <Field label="Confidence" value={`${(incident.confidence * 100).toFixed(1)}%`} />
          <Field label="Frames Confirmed" value={String(incident.frames_confirmed)} />
          <Field label="Weapon Count" value={String(incident.weapon_count)} />
          <Field label="Track ID" value={incident.track_id ? String(incident.track_id) : '—'} />
          <Field label="Created" value={format(new Date(incident.created_at), 'PPp')} />
          {incident.acknowledged_at && (
            <Field label="Acknowledged" value={`${format(new Date(incident.acknowledged_at), 'PPp')} by ${incident.acknowledged_by || '—'}`} />
          )}
          {incident.resolved_at && (
            <Field label="Resolved" value={`${format(new Date(incident.resolved_at), 'PPp')} by ${incident.resolved_by || '—'}`} />
          )}
          {incident.resolution_notes && (
            <div className="col-span-full">
              <span className="text-gray-400">Resolution Notes:</span>
              <p className="text-white mt-1">{incident.resolution_notes}</p>
            </div>
          )}
        </div>
      </div>

      {/* Evidence */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Evidence</h3>
        <EvidenceViewer incidentId={incident.id} />
      </div>

      {/* Actions */}
      {canModify && incident.status !== 'RESOLVED' && incident.status !== 'FALSE_POSITIVE' && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
          <h3 className="text-lg font-semibold mb-4">Actions</h3>
          <div className="flex gap-3">
            {incident.status === 'OPEN' && (
              <button
                onClick={() => handleStatusUpdate('ACKNOWLEDGED')}
                disabled={updating}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg text-sm font-medium"
              >
                Acknowledge
              </button>
            )}
            <button
              onClick={() => handleStatusUpdate('RESOLVED')}
              disabled={updating}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium"
            >
              Resolve
            </button>
            <button
              onClick={() => handleStatusUpdate('FALSE_POSITIVE')}
              disabled={updating}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg text-sm font-medium"
            >
              Mark False Positive
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-400">{label}:</span>
      <p className="text-white font-medium mt-0.5">{value}</p>
    </div>
  );
}
