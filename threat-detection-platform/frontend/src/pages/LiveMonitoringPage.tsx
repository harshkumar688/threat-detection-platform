import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Wifi, WifiOff, AlertTriangle, Activity } from 'lucide-react';
import { cameraService } from '../services/cameraService';
import { locationService } from '../services/locationService';
import { Camera as CameraType } from '../types/camera';
import { Location } from '../types/location';
import LoadingSpinner from '../components/common/LoadingSpinner';

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

interface Detection {
  class_name: string;
  confidence: number;
  is_weapon: boolean;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  track_id: number | null;
}

interface FramePayload {
  type: string;
  frame_b64?: string;
  frame_number?: number;
  detections?: Detection[];
  has_weapons?: boolean;
  risk_level?: string;
  risk_score?: number;
}

interface FeedState {
  connected: boolean;
  frameDataUrl: string | null;
  frameNumber: number;
  detections: Detection[];
  hasWeapons: boolean;
  riskLevel: string;
  riskScore: number;
  fps: number;
  error: string | null;
}

const INITIAL_FEED: FeedState = {
  connected: false,
  frameDataUrl: null,
  frameNumber: 0,
  detections: [],
  hasWeapons: false,
  riskLevel: 'LOW',
  riskScore: 0,
  fps: 0,
  error: null,
};

// ------------------------------------------------------------------
// Helper: build WebSocket URL
// ------------------------------------------------------------------

function buildWsUrl(cameraId: string): string {
  const token = localStorage.getItem('access_token') ?? '';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  // In Vite dev mode the page is on :3000 and Vite proxies /api to :8000,
  // but WebSocket connections bypass the Vite proxy; we connect directly.
  const host = window.location.hostname;
  return `${proto}://${host}:8000/api/v1/streams/feed/${encodeURIComponent(cameraId)}?token=${encodeURIComponent(token)}&fps=8&quality=65`;
}

// ------------------------------------------------------------------
// Live feed panel — one camera
// ------------------------------------------------------------------

function LiveFeedPanel({ camera, locationName }: { camera: CameraType; locationName: string }) {
  const wsRef = useRef<WebSocket | null>(null);
  const frameTimesRef = useRef<number[]>([]);
  const [feed, setFeed] = useState<FeedState>(INITIAL_FEED);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setFeed((s) => ({ ...s, error: null, connected: false, frameDataUrl: null }));

    const ws = new WebSocket(buildWsUrl(camera.id));
    wsRef.current = ws;

    ws.onopen = () => {
      setFeed((s) => ({ ...s, connected: true }));
    };

    ws.onmessage = (evt) => {
      try {
        const msg: FramePayload = JSON.parse(evt.data);
        if (msg.type === 'frame' && msg.frame_b64) {
          // Compute rolling FPS
          const now = performance.now();
          frameTimesRef.current.push(now);
          if (frameTimesRef.current.length > 20) frameTimesRef.current.shift();
          const oldest = frameTimesRef.current[0];
          const fps =
            frameTimesRef.current.length > 1
              ? Math.round(((frameTimesRef.current.length - 1) / ((now - oldest) / 1000)) * 10) / 10
              : 0;

          setFeed((s) => ({
            ...s,
            connected: true,
            frameDataUrl: `data:image/jpeg;base64,${msg.frame_b64}`,
            frameNumber: msg.frame_number ?? s.frameNumber + 1,
            detections: msg.detections ?? [],
            hasWeapons: msg.has_weapons ?? false,
            riskLevel: msg.risk_level ?? 'LOW',
            riskScore: msg.risk_score ?? 0,
            fps,
            error: null,
          }));
        } else if (msg.type === 'error') {
          setFeed((s) => ({ ...s, error: (msg as any).message ?? 'Stream error' }));
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      setFeed((s) => ({ ...s, error: 'WebSocket connection failed', connected: false }));
    };

    ws.onclose = (evt) => {
      setFeed((s) => ({
        ...s,
        connected: false,
        error: evt.code === 4008 ? 'Authentication failed' : s.error,
      }));
    };
  }, [camera.id]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    setFeed(INITIAL_FEED);
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const riskColor =
    feed.riskLevel === 'CRITICAL'
      ? 'text-red-500'
      : feed.riskLevel === 'HIGH'
      ? 'text-orange-400'
      : feed.riskLevel === 'MEDIUM'
      ? 'text-yellow-400'
      : 'text-green-400';

  return (
    <div
      className={`bg-gray-800 rounded-xl border overflow-hidden transition-colors ${
        feed.hasWeapons ? 'border-red-500' : feed.connected ? 'border-blue-500' : 'border-gray-700'
      }`}
    >
      {/* Video area */}
      <div className="relative aspect-video bg-gray-900">
        {feed.frameDataUrl ? (
          <img
            src={feed.frameDataUrl}
            alt={`Live feed: ${camera.name}`}
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-gray-600">
            <Camera className="w-12 h-12 mb-2" />
            <span className="text-sm">{feed.connected ? 'Waiting for frames…' : 'Not streaming'}</span>
          </div>
        )}

        {/* Overlays */}
        {feed.connected && (
          <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/60 px-2 py-1 rounded text-xs">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400 font-mono">LIVE</span>
          </div>
        )}

        {feed.fps > 0 && (
          <div className="absolute top-2 right-2 bg-black/60 px-2 py-1 rounded text-xs font-mono text-gray-300">
            {feed.fps} FPS
          </div>
        )}

        {feed.hasWeapons && (
          <div className="absolute bottom-2 left-2 flex items-center gap-1 bg-red-600/80 px-3 py-1 rounded-full text-xs font-bold animate-pulse">
            <AlertTriangle className="w-3 h-3" /> WEAPON DETECTED
          </div>
        )}

        {feed.error && (
          <div className="absolute bottom-2 left-2 bg-red-800/80 text-red-200 px-2 py-1 rounded text-xs">
            {feed.error}
          </div>
        )}
      </div>

      {/* Info strip */}
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-sm">{camera.name}</h3>
            <p className="text-xs text-gray-400">{locationName}</p>
          </div>
          <div className="flex gap-2">
            {!feed.connected ? (
              <button
                onClick={connect}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs flex items-center gap-1"
              >
                <Wifi className="w-3 h-3" /> Connect
              </button>
            ) : (
              <button
                onClick={disconnect}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs flex items-center gap-1"
              >
                <WifiOff className="w-3 h-3" /> Disconnect
              </button>
            )}
          </div>
        </div>

        {/* Detection stats */}
        {feed.connected && (
          <div className="grid grid-cols-3 gap-2 text-xs text-gray-400 border-t border-gray-700 pt-2">
            <div>
              <span className="block text-gray-500">Detections</span>
              <span className="text-white font-medium">{feed.detections.length}</span>
            </div>
            <div>
              <span className="block text-gray-500">Risk</span>
              <span className={`font-medium ${riskColor}`}>{feed.riskLevel}</span>
            </div>
            <div>
              <span className="block text-gray-500">Score</span>
              <span className="text-white font-medium">{feed.riskScore}/100</span>
            </div>
          </div>
        )}

        {/* Detection list */}
        {feed.connected && feed.detections.length > 0 && (
          <div className="space-y-1 border-t border-gray-700 pt-2">
            {feed.detections.slice(0, 4).map((d, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className={d.is_weapon ? 'text-red-400 font-semibold' : 'text-gray-300'}>
                  {d.is_weapon ? '⚠️ ' : ''}{d.class_name}
                </span>
                <span className="text-gray-500 font-mono">{(d.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Main page
// ------------------------------------------------------------------

export default function LiveMonitoringPage() {
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([cameraService.list(), locationService.list()])
      .then(([cams, locs]) => {
        setCameras(cams);
        setLocations(locs);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const locationName = (id: string | null) => {
    if (!id) return 'No location';
    return locations.find((l) => l.id === id)?.name || 'No location';
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          Live Monitoring
        </h2>
        <p className="text-xs text-gray-500">
          Click "Connect" on any camera to start the live feed.
        </p>
      </div>

      {cameras.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-500">
          <WifiOff className="w-12 h-12 mb-3" />
          <p className="text-lg">No cameras registered.</p>
          <p className="text-sm mt-1">
            Register a camera on the Cameras page, then come back here to monitor it live.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {cameras.map((cam) => (
            <LiveFeedPanel
              key={cam.id}
              camera={cam}
              locationName={locationName(cam.location_id)}
            />
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="text-xs text-gray-600 space-y-1">
        <p>• Frames are streamed as annotated JPEG via WebSocket from the backend detection pipeline.</p>
        <p>• A red border and "WEAPON DETECTED" banner indicate an active weapon detection in the current frame.</p>
        <p>• If YOLO libraries are not available in the backend environment, frames are streamed without detection overlay.</p>
      </div>
    </div>
  );
}
