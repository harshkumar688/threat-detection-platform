// Common shared types

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  status: string;
  data: T[];
  meta: PaginationMeta;
}

export interface ApiError {
  status: string;
  error: {
    code: string;
    message: string;
    details?: any;
  };
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type IncidentStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_POSITIVE';
export type UserRole = 'admin' | 'operator' | 'viewer';
export type CameraStatus = 'online' | 'offline' | 'processing' | 'error';
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
