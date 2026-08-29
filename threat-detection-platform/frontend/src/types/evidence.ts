export interface EvidenceItem {
  id: string;
  incident_id: string;
  evidence_type: 'snapshot' | 'clip';
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  camera_id: string;
  captured_at: string;
  expires_at: string | null;
  is_expired: boolean;
  privacy_mode_applied: 'off' | 'face_blur' | 'face_pixelate';
  faces_anonymized: number;
}

export interface EvidenceListResponse {
  incident_id: string;
  items: EvidenceItem[];
  total: number;
}
