import { Sliders } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-xl font-semibold">System Settings</h2>

      {/* Detection Settings */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Sliders className="w-5 h-5 text-blue-400" /> Detection Parameters
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingField label="Confidence Threshold" value="0.50" description="Minimum detection confidence" />
          <SettingField label="NMS IoU Threshold" value="0.45" description="Non-maximum suppression overlap" />
          <SettingField label="Input Resolution" value="640" description="Model input size (px)" />
          <SettingField label="Device" value="auto" description="Inference device (auto/cpu/cuda)" />
        </div>
      </div>

      {/* Verification Settings */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Multi-Frame Verification</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingField label="Required Hits (N)" value="3" description="Frames needed in window" />
          <SettingField label="Window Size (M)" value="5" description="Sliding window frames" />
          <SettingField label="Confirm Frames" value="3" description="Frames to sustain CANDIDATE" />
          <SettingField label="Grace Period" value="5" description="Missed frames tolerated" />
        </div>
      </div>

      {/* Scoring Settings */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Risk Scoring Weights</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingField label="Weapon Severity" value="0.30" description="Weight for weapon class" />
          <SettingField label="Confidence" value="0.25" description="Weight for detection confidence" />
          <SettingField label="Persistence" value="0.20" description="Weight for time visible" />
          <SettingField label="Weapon Count" value="0.15" description="Weight for multiple weapons" />
          <SettingField label="Location" value="0.10" description="Weight for location sensitivity" />
        </div>
      </div>

      <p className="text-gray-500 text-sm">
        Settings are loaded from environment variables. Live editing requires the config API module.
      </p>
    </div>
  );
}

function SettingField({ label, value, description }: { label: string; value: string; description: string }) {
  return (
    <div>
      <label className="text-sm text-gray-400">{label}</label>
      <input
        type="text"
        value={value}
        readOnly
        className="w-full mt-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm"
      />
      <p className="text-xs text-gray-500 mt-1">{description}</p>
    </div>
  );
}
