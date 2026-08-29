export interface Location {
  id: string;
  name: string;
  building: string;
  floor: string;
  zone: string;
  description: string;
  latitude: number | null;
  longitude: number | null;
  is_active: boolean;
  created_at: string;
}

export interface LocationCreateInput {
  name: string;
  building?: string;
  floor?: string;
  zone?: string;
  description?: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface LocationUpdateInput {
  name?: string;
  building?: string;
  floor?: string;
  zone?: string;
  description?: string;
  latitude?: number | null;
  longitude?: number | null;
  is_active?: boolean;
}
