import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Meeting } from '../../types/meeting';
import { MeetingCard } from './MeetingCard';

interface RecentMeetingsListProps {
  meetings: Meeting[];
  selectedMeetingId?: string;
  onSelectMeeting?: (meeting: Meeting) => void;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export const RecentMeetingsList: React.FC<RecentMeetingsListProps> = ({
  meetings,
  selectedMeetingId,
  onSelectMeeting,
  isLoading = false,
  error = null,
  onRetry,
}) => {
  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-[#141522] tracking-tight">Recent Meetings</h2>
        <button
          type="button"
          className="text-xs font-semibold text-[#5932ea] hover:text-[#4b27d6] flex items-center gap-1 cursor-pointer transition-colors"
          onClick={() => {
            if (meetings.length > 0 && onSelectMeeting) {
              onSelectMeeting(meetings[0]);
            }
          }}
        >
          <span>Go to Meetings</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-gray-400">Loading recent meetings...</div>
      ) : error ? (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center">
          <p className="text-xs text-rose-600 mb-2">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="text-xs font-semibold text-[#5932ea] underline"
            >
              Retry
            </button>
          )}
        </div>
      ) : meetings.length === 0 ? (
        <div className="py-8 text-center text-xs text-gray-400">No meetings available.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          {meetings.slice(0, 2).map((meeting) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              isSelected={selectedMeetingId === meeting.id}
              onSelect={onSelectMeeting}
            />
          ))}
        </div>
      )}
    </div>
  );
};
