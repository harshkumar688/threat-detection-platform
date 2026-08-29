import { CameraStatus } from './common';

export interface Camera {
  id: string;
  name: string;
  location_id: string | null;
  stream_url: string;
  stream_type: string;
  target_fps: number;
  resolution_width: number | null;
  resolution_height: number | null;
  status: CameraStatus;
  is_enabled: boolean;
  last_online_at: string | null;
  error_message: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

export interface CameraCreateInput {
  name: string;
  location_id?: string | null;
  stream_url: string;
  stream_type?: string;
  target_fps?: number;
  is_enabled?: boolean;
  metadata?: Record<string, any>;
}

export interface CameraUpdateInput {
  name?: string;
  location_id?: string | null;
  stream_url?: string;
  stream_type?: string;
  target_fps?: number;
  is_enabled?: boolean;
  metadata?: Record<string, any>;
}
