import { FileImage, Film, Clock } from 'lucide-react';

export default function EvidencePage() {
  return (
    <div className="space-y-6">
      <p className="text-gray-400">
        Evidence is accessed from individual incident detail pages.
        Navigate to an incident to view its associated snapshots and video clips.
      </p>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Evidence Types</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-4 bg-gray-700/50 rounded-lg">
            <FileImage className="w-8 h-8 text-blue-400" />
            <div>
              <h4 className="font-medium">Snapshots</h4>
              <p className="text-sm text-gray-400">Annotated frame at detection time</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4 bg-gray-700/50 rounded-lg">
            <Film className="w-8 h-8 text-green-400" />
            <div>
              <h4 className="font-medium">Video Clips</h4>
              <p className="text-sm text-gray-400">Pre/post event recording</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4 bg-gray-700/50 rounded-lg">
            <Clock className="w-8 h-8 text-yellow-400" />
            <div>
              <h4 className="font-medium">Retention</h4>
              <p className="text-sm text-gray-400">90-day auto-cleanup</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
