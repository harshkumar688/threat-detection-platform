import { useEffect, useState } from 'react';
import { Camera, Wifi, WifiOff } from 'lucide-react';
import { cameraService } from '../services/cameraService';
import { locationService } from '../services/locationService';
import { Camera as CameraType } from '../types/camera';
import { Location } from '../types/location';
import StatusBadge from '../components/common/StatusBadge';
import SeverityBadge from '../components/common/SeverityBadge';

export default function LiveMonitoringPage() {
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);

  useEffect(() => {
    cameraService.list().then(setCameras).catch(console.error);
    locationService.list().then(setLocations).catch(console.error);
  }, []);

  const locationName = (id: string | null) => {
    if (!id) return 'No location';
    return locations.find((l) => l.id === id)?.name || 'No location';
  };

  const activeCameras = cameras.filter((c) => c.status === 'processing' || c.status === 'online');

  return (
    <div className="space-y-6">
      {/* Camera Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activeCameras.length > 0 ? (
          activeCameras.map((cam) => (
            <div
              key={cam.id}
              onClick={() => setSelectedCamera(cam.id)}
              className={`bg-gray-800 rounded-xl border cursor-pointer transition-colors ${
                selectedCamera === cam.id ? 'border-blue-500' : 'border-gray-700 hover:border-gray-600'
              }`}
            >
              {/* Video Feed Placeholder */}
              <div className="aspect-video bg-gray-900 rounded-t-xl flex items-center justify-center relative">
                <Camera className="w-12 h-12 text-gray-600" />
                <div className="absolute top-2 left-2 flex items-center gap-1">
                  <Wifi className="w-3 h-3 text-green-400" />
                  <span className="text-xs text-green-400">LIVE</span>
                </div>
                <div className="absolute top-2 right-2">
                  <StatusBadge status={cam.status} />
                </div>
                {/* Detection overlay info would go here */}
                <div className="absolute bottom-2 left-2 text-xs text-gray-300 bg-black/50 px-2 py-1 rounded">
                  {cam.target_fps} FPS | {cam.stream_type.toUpperCase()}
                </div>
              </div>

              {/* Camera Info */}
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-sm">{cam.name}</h3>
                </div>
                <p className="text-xs text-gray-400 mt-1">{locationName(cam.location_id)}</p>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full flex flex-col items-center justify-center py-12 text-gray-500">
            <WifiOff className="w-12 h-12 mb-3" />
            <p className="text-lg">No active cameras</p>
            <p className="text-sm mt-1">Start processing on a camera to begin monitoring.</p>
          </div>
        )}
      </div>

      {/* Selected Camera Detail */}
      {selectedCamera && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
          <h3 className="text-lg font-semibold mb-4">Detection Feed</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Track IDs:</span>
              <span className="ml-2 text-white">—</span>
            </div>
            <div>
              <span className="text-gray-400">Detections:</span>
              <span className="ml-2 text-white">0</span>
            </div>
            <div>
              <span className="text-gray-400">Confidence:</span>
              <span className="ml-2 text-white">—</span>
            </div>
            <div>
              <span className="text-gray-400">Risk Level:</span>
              <span className="ml-2"><SeverityBadge level="LOW" /></span>
            </div>
          </div>
          <p className="text-gray-500 text-sm mt-4">
            Live detection overlay requires WebSocket connection to the detection pipeline.
            Connect a camera and start processing to see real-time detections.
          </p>
        </div>
      )}

      {/* All Cameras List */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">All Cameras ({cameras.length})</h3>
        <div className="space-y-2">
          {cameras.map((cam) => (
            <div key={cam.id} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
              <div className="flex items-center gap-3">
                <Camera className="w-4 h-4 text-gray-400" />
                <span className="text-sm">{cam.name}</span>
                <span className="text-xs text-gray-500">{locationName(cam.location_id)}</span>
              </div>
              <StatusBadge status={cam.status} />
            </div>
          ))}
          {cameras.length === 0 && <p className="text-gray-500 text-sm">No cameras registered.</p>}
        </div>
      </div>
    </div>
  );
}
