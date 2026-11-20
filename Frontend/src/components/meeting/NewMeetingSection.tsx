import React, { useState, useRef } from 'react';
import { Video, UploadCloud, ChevronDown } from 'lucide-react';
import { JoinMeetingPayload, UploadMeetingPayload } from '../../types/meeting';

interface NewMeetingSectionProps {
  onJoinMeeting: (payload: JoinMeetingPayload) => Promise<unknown>;
  onUploadMeeting: (payload: UploadMeetingPayload) => Promise<unknown>;
  isSubmitting?: boolean;
}

export const NewMeetingSection: React.FC<NewMeetingSectionProps> = ({
  onJoinMeeting,
  onUploadMeeting,
  isSubmitting = false,
}) => {
  const [activeTab, setActiveTab] = useState<'online' | 'upload'>('online');
  const [meetingUrl, setMeetingUrl] = useState('');
  const [language, setLanguage] = useState('English');
  const [slotName, setSlotName] = useState('Chatmeet');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!meetingUrl.trim()) {
      setError('Please paste a meeting URL.');
      return;
    }
    try {
      await onJoinMeeting({
        meeting_url: meetingUrl.trim(),
        language,
        slot_name: slotName || 'Chatmeet',
      });
      setMeetingUrl('');
    } catch (err: unknown) {
      setError((err as Error)?.message || 'Failed to join meeting.');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }
    try {
      await onUploadMeeting({
        file: selectedFile,
        language,
        slot_name: slotName || 'Chatmeet',
      });
      setSelectedFile(null);
    } catch (err: unknown) {
      setError((err as Error)?.message || 'Failed to upload meeting.');
    }
  };

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-bold text-[#141522] tracking-tight">New Meeting</h2>

      <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
        {/* Top row: Online meeting pill & Upload meeting immediately beside */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setActiveTab('online');
              setError(null);
            }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
              activeTab === 'online'
                ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
                : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300'
            }`}
          >
            <Video className="w-4 h-4 text-[#5932ea]" />
            <span>Online meeting</span>
          </button>

          {/* Strict requirement 4: Upload Meeting option immediately beside Online Meeting */}
          <button
            type="button"
            onClick={() => {
              setActiveTab('upload');
              setError(null);
            }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
              activeTab === 'upload'
                ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
                : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300'
            }`}
          >
            <UploadCloud className="w-4 h-4 text-[#5932ea]" />
            <span>Upload meeting</span>
          </button>
        </div>

        {/* Input & Action Button row */}
        {activeTab === 'online' ? (
          <form onSubmit={handleJoin} className="flex items-center gap-3 min-w-0">
            <div className="flex-1 min-w-0 flex items-center justify-between border border-gray-200 rounded-xl px-4 py-2.5 bg-white focus-within:border-[#5932ea] transition-colors">
              <input
                type="text"
                value={meetingUrl}
                onChange={(e) => {
                  setMeetingUrl(e.target.value);
                  if (error) setError(null);
                }}
                placeholder="Paste your meeting URL here"
                className="w-full text-sm text-[#141522] placeholder:text-gray-400 focus:outline-none"
                disabled={isSubmitting}
              />
              {/* Meeting platform logos */}
              <div className="flex items-center gap-1.5 pl-2 shrink-0">
                {/* Google Meet icon */}
                <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold text-red-500">
                  G
                </span>
                {/* Drive / Teams triangle icon */}
                <span className="w-3.5 h-3.5 text-blue-500 font-bold text-[10px]">
                  ▲
                </span>
                {/* Users icon */}
                <span className="w-3.5 h-3.5 text-purple-600 font-bold text-[10px]">
                  👥
                </span>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-[#5932ea] hover:bg-[#4b27d6] text-white text-sm font-semibold px-5 sm:px-6 py-2.5 sm:py-3 rounded-xl transition-colors shrink-0 shadow-xs cursor-pointer disabled:opacity-60"
            >
              {isSubmitting ? 'Joining...' : 'Join Now'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleUpload} className="flex items-center gap-3 min-w-0">
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setSelectedFile(e.target.files[0]);
                  setError(null);
                }
              }}
              accept="audio/*,video/*,.mp4,.mp3,.wav,.m4a"
              className="hidden"
            />
            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 min-w-0 flex items-center justify-between border border-dashed border-gray-300 hover:border-[#5932ea] rounded-xl px-4 py-2.5 bg-gray-50/50 cursor-pointer transition-colors"
            >
              <span className="text-sm text-gray-500 truncate">
                {selectedFile ? selectedFile.name : 'Select or drop recorded meeting file (MP4, MP3, WAV)...'}
              </span>
              <span className="text-xs text-[#5932ea] font-medium shrink-0 ml-2">Browse</span>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-[#5932ea] hover:bg-[#4b27d6] text-white text-sm font-semibold px-5 sm:px-6 py-2.5 sm:py-3 rounded-xl transition-colors shrink-0 shadow-xs cursor-pointer disabled:opacity-60"
            >
              {isSubmitting ? 'Uploading...' : 'Upload Now'}
            </button>
          </form>
        )}

        {error && <p className="text-xs text-rose-600">{error}</p>}

        {/* Bottom row: Language & Slot name */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          {/* Language field */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Language</label>
            <div className="border border-gray-200 rounded-xl px-3.5 py-2.5 flex items-center justify-between bg-white cursor-pointer hover:border-gray-300 transition-colors">
              <div className="flex items-center gap-2">
                <span className="text-sm">🇬🇧</span>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="text-sm font-medium text-[#141522] bg-transparent focus:outline-none cursor-pointer pr-2"
                >
                  <option value="English">English</option>
                  <option value="Spanish">Spanish</option>
                  <option value="French">French</option>
                  <option value="German">German</option>
                </select>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            </div>
          </div>

          {/* Slot name field */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Slot name</label>
            <div className="border border-gray-200 rounded-xl px-3.5 py-2.5 flex items-center bg-white focus-within:border-[#5932ea] transition-colors">
              <input
                type="text"
                value={slotName}
                onChange={(e) => setSlotName(e.target.value)}
                placeholder="Chatmeet"
                className="w-full text-sm font-medium text-[#141522] placeholder:text-gray-400 focus:outline-none bg-transparent"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
