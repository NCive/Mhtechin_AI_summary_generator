import React from 'react';
import { Calendar, Clock, Folder, Users, MoreHorizontal } from 'lucide-react';
import { Meeting } from '../../types/meeting';

interface MeetingCardProps {
  meeting: Meeting;
  isSelected?: boolean;
  onSelect?: (meeting: Meeting) => void;
}

export const MeetingCard: React.FC<MeetingCardProps> = ({
  meeting,
  isSelected = false,
  onSelect,
}) => {
  return (
    <div
      onClick={() => onSelect && onSelect(meeting)}
      className={`bg-white rounded-2xl p-4 border transition-all duration-200 cursor-pointer flex flex-col justify-between hover:shadow-md ${
        isSelected
          ? 'border-[#5932ea] shadow-[0_4px_16px_rgba(89,50,234,0.08)] ring-1 ring-[#5932ea]'
          : 'border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] hover:border-gray-300'
      }`}
    >
      <div>
        {/* Title & More */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="text-sm font-bold text-[#141522] truncate tracking-tight">
            {meeting.title}
          </h3>
          <button
            type="button"
            className="text-gray-400 hover:text-gray-600 p-0.5 rounded cursor-pointer"
            onClick={(e) => e.stopPropagation()}
            aria-label="Options"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>

        {/* Date, duration, users */}
        <div className="flex items-center gap-2 text-[11px] text-gray-500 mb-2.5">
          {meeting.date ? (
            <div className="flex items-center gap-1">
              <Calendar className="w-3 h-3 text-gray-400" />
              <span>{meeting.date}</span>
            </div>
          ) : null}
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-gray-400" />
            <span>{meeting.durationLabel || (meeting.durationSeconds ? `${Math.round(meeting.durationSeconds / 60)}m` : '—')}</span>
          </div>
          <Users className="w-3 h-3 text-gray-400" />
        </div>

        {/* Snippet */}
        <p className="text-xs text-gray-500 leading-relaxed line-clamp-3 mb-4">
          {meeting.summarySnippet}
        </p>
      </div>

      {/* Bottom: Folder badge & avatars */}
      <div className="flex items-center justify-between pt-2">
        {meeting.folder ? (
          <span className="inline-flex items-center gap-1.5 bg-[#f0edff] text-[#5932ea] text-[11px] font-medium px-2.5 py-1 rounded-md">
            <Folder className="w-3 h-3 fill-current text-[#5932ea]" />
            <span>{meeting.folder}</span>
          </span>
        ) : (
          <div />
        )}

        {/* Avatars */}
        <div className="flex items-center -space-x-1.5">
          {meeting.participantAvatars && meeting.participantAvatars.length > 0 ? (
            <>
              {meeting.participantAvatars.slice(0, 2).map((avatar, idx) => (
                <img
                  key={idx}
                  src={avatar}
                  alt="Participant"
                  className="w-5 h-5 rounded-full object-cover ring-1.5 ring-white"
                />
              ))}
              {meeting.participantsCount > 2 && (
                <span className="text-[11px] font-semibold text-[#5932ea] pl-2">
                  +{meeting.participantsCount - 2}
                </span>
              )}
            </>
          ) : meeting.participantsCount != null && meeting.participantsCount > 0 ? (
            <span className="text-[11px] font-medium text-gray-500">
              {meeting.participantsCount} participants
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
};
