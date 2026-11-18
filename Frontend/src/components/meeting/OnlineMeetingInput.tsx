import React, { useState } from 'react';
import { Video, ArrowRight, Link as LinkIcon } from 'lucide-react';
import { Button } from '../common/Button';

interface OnlineMeetingInputProps {
  onJoin: (meetingUrl: string) => Promise<void>;
  isLoading?: boolean;
}

export const OnlineMeetingInput: React.FC<OnlineMeetingInputProps> = ({
  onJoin,
  isLoading = false,
}) => {
  const [meetingUrl, setMeetingUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!meetingUrl.trim()) {
      setError('Please provide an online meeting URL (e.g. Google Meet, Zoom, Teams).');
      return;
    }

    try {
      new URL(meetingUrl.trim());
    } catch {
      setError('Please enter a valid URL (starting with https://).');
      return;
    }

    try {
      await onJoin(meetingUrl.trim());
      setMeetingUrl('');
    } catch (err: unknown) {
      setError((err as Error)?.message || 'Failed to join meeting.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        <div className="relative flex-1">
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
            <LinkIcon className="w-4 h-4" />
          </div>
          <input
            type="url"
            value={meetingUrl}
            onChange={(e) => {
              setMeetingUrl(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Paste Google Meet, Teams, or Zoom URL..."
            className="w-full pl-10 pr-3 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-xs"
            disabled={isLoading}
          />
        </div>
        <Button
          type="submit"
          variant="primary"
          size="md"
          isLoading={isLoading}
          icon={<Video className="w-4 h-4" />}
          className="shrink-0 font-semibold"
        >
          <span>Join Now</span>
          <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
        </Button>
      </div>
      {error && <p className="mt-1.5 text-xs text-rose-600 font-medium">{error}</p>}
    </form>
  );
};
