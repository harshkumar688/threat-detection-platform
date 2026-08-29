import api from './api';
import { EvidenceListResponse } from '../types/evidence';

export const evidenceService = {
  listForIncident: async (incidentId: string): Promise<EvidenceListResponse> => {
    const res = await api.get<EvidenceListResponse>(`/evidence/${incidentId}`);
    return res.data;
  },

  /**
   * Builds an authenticated download URL for an evidence file.
   * The browser will need the Authorization header attached (handled via
   * fetchEvidenceBlob) since <img src> cannot carry custom headers.
   */
  fetchEvidenceBlob: async (evidenceId: string): Promise<string> => {
    const res = await api.get(`/evidence/file/${evidenceId}`, { responseType: 'blob' });
    return URL.createObjectURL(res.data);
  },
};
