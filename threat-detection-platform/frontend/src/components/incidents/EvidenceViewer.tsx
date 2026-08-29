import { useEffect, useState } from 'react';
import { FileImage, Film, Download, ShieldCheck } from 'lucide-react';
import { evidenceService } from '../../services/evidenceService';
import { EvidenceItem } from '../../types/evidence';
import { format } from 'date-fns';
import { useAuthStore } from '../../store/authStore';

interface Props {
  incidentId: string;
}

export default function EvidenceViewer({ incidentId }: Props) {
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({});
  const [downloadError, setDownloadError] = useState('');
  const { user } = useAuthStore();
  // Evidence file download is restricted to admin/operator roles (see
  // backend app/auth/permissions.py) — viewers can see that evidence
  // exists but cannot fetch the media itself.
  const canDownload = user?.role === 'admin' || user?.role === 'operator';

  useEffect(() => {
    evidenceService
      .listForIncident(incidentId)
      .then((res) => setItems(res.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [incidentId]);

  useEffect(() => {
    if (!canDownload) return; // Viewers lack DOWNLOAD_EVIDENCE — skip thumbnail fetch entirely.
    // Lazy-load thumbnails for snapshot evidence
    items
      .filter((item) => item.evidence_type === 'snapshot')
      .forEach((item) => {
        if (thumbnails[item.id]) return;
        evidenceService
          .fetchEvidenceBlob(item.id)
          .then((url) => setThumbnails((prev) => ({ ...prev, [item.id]: url })))
          .catch(() => null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, canDownload]);

  const handleDownload = async (item: EvidenceItem) => {
    setDownloadError('');
    try {
      const url = await evidenceService.fetchEvidenceBlob(item.id);
      const a = document.createElement('a');
      a.href = url;
      a.download = item.file_name;
      a.click();
    } catch {
      setDownloadError('Failed to download evidence file.');
    }
  };

  if (loading) {
    return <p className="text-gray-500 text-sm">Loading evidence...</p>;
  }

  if (items.length === 0) {
    return (
      <p className="text-gray-500 text-sm">
        No evidence has been captured for this incident yet.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {downloadError && (
        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs">
          {downloadError}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((item) => (
          <div key={item.id} className="bg-gray-700/50 rounded-lg border border-gray-700 overflow-hidden">
            <div className="aspect-video bg-gray-900 flex items-center justify-center">
              {item.evidence_type === 'snapshot' && thumbnails[item.id] ? (
                <img src={thumbnails[item.id]} alt="Evidence snapshot" className="w-full h-full object-cover" />
              ) : item.evidence_type === 'snapshot' ? (
                <FileImage className="w-10 h-10 text-gray-600" />
              ) : (
                <Film className="w-10 h-10 text-gray-600" />
              )}
            </div>
            <div className="p-3 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{item.evidence_type}</span>
                {canDownload ? (
                  <button
                    onClick={() => handleDownload(item)}
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    <Download className="w-3 h-3" /> Download
                  </button>
                ) : (
                  <span className="text-gray-500 text-[11px]">Restricted</span>
                )}
              </div>
              <p className="text-gray-400">{format(new Date(item.captured_at), 'PPp')}</p>
              <p className="text-gray-500">
                {(item.file_size_bytes / 1024).toFixed(1)} KB
                {item.duration_seconds ? ` · ${item.duration_seconds.toFixed(1)}s` : ''}
              </p>
              {item.privacy_mode_applied !== 'off' && (
                <p className="flex items-center gap-1 text-green-400">
                  <ShieldCheck className="w-3 h-3" />
                  {item.faces_anonymized > 0
                    ? `${item.faces_anonymized} face(s) anonymized`
                    : 'Privacy mode active'}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
