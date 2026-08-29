import { useEffect, useState } from 'react';
import { Camera, Play, Square, Trash2, Plus, X, MapPin } from 'lucide-react';
import { cameraService } from '../services/cameraService';
import { locationService } from '../services/locationService';
import { Camera as CameraType } from '../types/camera';
import { Location } from '../types/location';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useAuthStore } from '../store/authStore';

const NEW_LOCATION_VALUE = '__new__';

export default function CamerasPage() {
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';
  const canOperate = user?.role === 'admin' || user?.role === 'operator';

  const load = () => {
    setLoading(true);
    Promise.all([cameraService.list(), locationService.list()])
      .then(([cams, locs]) => {
        setCameras(cams);
        setLocations(locs);
      })
      .catch(() => setError('Failed to load cameras/locations.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const locationName = (id: string | null) => {
    if (!id) return '—';
    return locations.find((l) => l.id === id)?.name || '—';
  };

  const handleStart = async (id: string) => {
    const updated = await cameraService.start(id);
    setCameras((prev) => prev.map((c) => (c.id === id ? updated : c)));
  };

  const handleStop = async (id: string) => {
    const updated = await cameraService.stop(id);
    setCameras((prev) => prev.map((c) => (c.id === id ? updated : c)));
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Remove this camera? This cannot be undone.')) return;
    try {
      await cameraService.delete(id);
      setCameras((prev) => prev.filter((c) => c.id !== id));
    } catch {
      setError('Failed to delete camera.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Cameras ({cameras.length})</h2>
        {isAdmin && (
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm"
          >
            <Plus className="w-4 h-4" /> Add Camera
          </button>
        )}
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div key={cam.id} className="bg-gray-800 rounded-xl border border-gray-700 p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Camera className="w-5 h-5 text-gray-400" />
                  <h3 className="font-medium">{cam.name}</h3>
                </div>
                <StatusBadge status={cam.status} />
              </div>

              <div className="space-y-2 text-sm text-gray-400">
                <p className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" /> {locationName(cam.location_id)}
                </p>
                <p>URL: <span className="text-xs font-mono">{cam.stream_url}</span></p>
                <p>FPS: {cam.target_fps} | Type: {cam.stream_type}</p>
                {cam.error_message && (
                  <p className="text-red-400 text-xs">Error: {cam.error_message}</p>
                )}
              </div>

              {canOperate && (
                <div className="flex gap-2 mt-4">
                  {cam.status !== 'processing' ? (
                    <button
                      onClick={() => handleStart(cam.id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-green-600/20 text-green-400 rounded text-xs hover:bg-green-600/30"
                    >
                      <Play className="w-3 h-3" /> Start
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStop(cam.id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-red-600/20 text-red-400 rounded text-xs hover:bg-red-600/30"
                    >
                      <Square className="w-3 h-3" /> Stop
                    </button>
                  )}
                  {isAdmin && (
                    <button
                      onClick={() => handleDelete(cam.id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 text-gray-400 rounded text-xs hover:bg-gray-600"
                    >
                      <Trash2 className="w-3 h-3" /> Remove
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
          {cameras.length === 0 && (
            <p className="col-span-full text-gray-500 text-center py-8">No cameras registered.</p>
          )}
        </div>
      )}

      {showForm && (
        <AddCameraModal
          locations={locations}
          onClose={() => setShowForm(false)}
          onCreated={(cam, newLocations) => {
            setCameras((prev) => [...prev, cam]);
            if (newLocations) setLocations(newLocations);
            setShowForm(false);
          }}
        />
      )}
    </div>
  );
}

function AddCameraModal({
  locations,
  onClose,
  onCreated,
}: {
  locations: Location[];
  onClose: () => void;
  onCreated: (cam: CameraType, newLocations?: Location[]) => void;
}) {
  const [name, setName] = useState('');
  const [streamUrl, setStreamUrl] = useState('');
  const [streamType, setStreamType] = useState('rtsp');
  const [targetFps, setTargetFps] = useState(15);
  const [locationChoice, setLocationChoice] = useState('');
  const [newLocName, setNewLocName] = useState('');
  const [newLocBuilding, setNewLocBuilding] = useState('');
  const [newLocZone, setNewLocZone] = useState('');
  const [newLocLat, setNewLocLat] = useState('');
  const [newLocLng, setNewLocLng] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      let locationId: string | undefined;
      let updatedLocations: Location[] | undefined;

      if (locationChoice === NEW_LOCATION_VALUE) {
        if (!newLocName.trim()) {
          setError('Location name is required.');
          setSubmitting(false);
          return;
        }
        const created = await locationService.create({
          name: newLocName,
          building: newLocBuilding || undefined,
          zone: newLocZone || undefined,
          latitude: newLocLat ? parseFloat(newLocLat) : null,
          longitude: newLocLng ? parseFloat(newLocLng) : null,
        });
        locationId = created.id;
        updatedLocations = [...locations, created];
      } else if (locationChoice) {
        locationId = locationChoice;
      }

      const cam = await cameraService.create({
        name,
        stream_url: streamUrl,
        stream_type: streamType,
        target_fps: targetFps,
        location_id: locationId || null,
      });
      onCreated(cam, updatedLocations);
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || 'Failed to create camera.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 w-full max-w-md p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Add Camera</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="p-2 mb-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Field label="Camera Name">
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="e.g. Lobby Cam 1"
            />
          </Field>

          <Field label="Stream URL">
            <input
              required
              value={streamUrl}
              onChange={(e) => setStreamUrl(e.target.value)}
              className="input"
              placeholder="rtsp://192.168.1.10/stream"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Stream Type">
              <select value={streamType} onChange={(e) => setStreamType(e.target.value)} className="input">
                <option value="rtsp">RTSP</option>
                <option value="http">HTTP</option>
                <option value="usb">USB</option>
                <option value="file">File</option>
              </select>
            </Field>
            <Field label="Target FPS">
              <input
                type="number"
                min={1}
                max={60}
                value={targetFps}
                onChange={(e) => setTargetFps(parseInt(e.target.value, 10) || 15)}
                className="input"
              />
            </Field>
          </div>

          <Field label="Location">
            <select
              value={locationChoice}
              onChange={(e) => setLocationChoice(e.target.value)}
              className="input"
            >
              <option value="">No location</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
              <option value={NEW_LOCATION_VALUE}>+ New Location...</option>
            </select>
          </Field>

          {locationChoice === NEW_LOCATION_VALUE && (
            <div className="space-y-3 p-3 bg-gray-750 border border-gray-700 rounded-lg">
              <Field label="Location Name">
                <input
                  required
                  value={newLocName}
                  onChange={(e) => setNewLocName(e.target.value)}
                  className="input"
                  placeholder="e.g. Main Entrance Lobby"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Building">
                  <input value={newLocBuilding} onChange={(e) => setNewLocBuilding(e.target.value)} className="input" />
                </Field>
                <Field label="Zone">
                  <input value={newLocZone} onChange={(e) => setNewLocZone(e.target.value)} className="input" />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Latitude">
                  <input
                    type="number"
                    step="any"
                    value={newLocLat}
                    onChange={(e) => setNewLocLat(e.target.value)}
                    className="input"
                    placeholder="optional"
                  />
                </Field>
                <Field label="Longitude">
                  <input
                    type="number"
                    step="any"
                    value={newLocLng}
                    onChange={(e) => setNewLocLng(e.target.value)}
                    className="input"
                    placeholder="optional"
                  />
                </Field>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-700 rounded-lg text-sm hover:bg-gray-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Camera'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-400 mb-1">{label}</span>
      {children}
    </label>
  );
}
