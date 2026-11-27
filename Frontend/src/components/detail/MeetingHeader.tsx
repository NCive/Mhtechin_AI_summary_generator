import React, { useState } from 'react';
import {
  ArrowLeft,
  Calendar,
  Clock,
  Folder,
  Share2,
  Upload,
  MoreHorizontal,
  Users,
  Check,
} from 'lucide-react';
import { MeetingDetail } from '../../types/meeting';
import { useShare } from '../../hooks/useShare';
import { exportToBrowserPdf } from '../../utils/exportPdf';
import { Toast } from '../common/Toast';

interface MeetingHeaderProps {
  meeting: MeetingDetail;
  onBack?: () => void;
}

export const MeetingHeader: React.FC<MeetingHeaderProps> = ({ meeting, onBack }) => {
  const { share, copied } = useShare();
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const title = meeting?.title || 'Meeting Details';
  const folder = meeting?.folder;
  const date = meeting?.date;

  const getDurationText = (): string | undefined => {
    if (meeting?.durationSeconds != null && meeting.durationSeconds > 0) {
      if (meeting.durationSeconds < 60) {
        return '<1 min';
      }
      const mins = Math.round(meeting.durationSeconds / 60);
      return mins <= 1 ? '1 min' : `${mins} mins`;
    }
    if (meeting?.timeRange && meeting.timeRange.trim() && meeting.timeRange !== '0 mins') {
      return meeting.timeRange;
    }
    return undefined;
  };

  const durationText = getDurationText();

  const handleShare = async () => {
    const success = await share({
      title,
      text: `Meeting Summary for ${title} (${folder})`,
      url: window.location.href,
    });
    if (success) {
      setToastMessage('Meeting link copied to clipboard!');
    }
  };

  const handleExport = () => {
    exportToBrowserPdf(title);
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
      {/* Left: Back button & Title info */}
      <div className="flex items-center gap-3">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="w-9 h-9 rounded-xl bg-white border border-gray-200 flex items-center justify-center text-gray-700 hover:bg-gray-50 cursor-pointer shadow-xs transition-colors shrink-0"
            aria-label="Back"
          >
            <ArrowLeft className="w-4 h-4 text-gray-700" />
          </button>
        )}

        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-[#141522] tracking-tight">
              {title}
            </h1>
            {folder && (
              <span className="inline-flex items-center gap-1.5 bg-[#f0edff] text-[#5932ea] text-xs font-medium px-2.5 py-0.5 rounded-md">
                <Folder className="w-3 h-3 fill-current text-[#5932ea]" />
                <span>{folder}</span>
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 mt-1">
            {date && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                <span>{date}</span>
              </div>
            )}
            {durationText && (
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span>{durationText}</span>
              </div>
            )}
            <Users className="w-3.5 h-3.5 text-purple-600 font-bold" />
          </div>
        </div>
      </div>

      {/* Right: Share, Export, More */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={handleShare}
          className="bg-white hover:bg-gray-50 border border-gray-200 text-[#141522] text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-emerald-600" />
          ) : (
            <Share2 className="w-3.5 h-3.5 text-gray-600" />
          )}
          <span>{copied ? 'Copied' : 'Share'}</span>
        </button>

        <button
          type="button"
          onClick={handleExport}
          className="bg-white hover:bg-gray-50 border border-gray-200 text-[#141522] text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
        >
          <Upload className="w-3.5 h-3.5 text-gray-600" />
          <span>Export</span>
        </button>

        <button
          type="button"
          className="bg-white hover:bg-gray-50 border border-gray-200 text-gray-600 px-3 py-2 rounded-xl flex items-center justify-center shadow-xs transition-colors cursor-pointer"
          aria-label="More options"
        >
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </div>

      {toastMessage && (
        <Toast
          isOpen={!!toastMessage}
          message={toastMessage}
          onClose={() => setToastMessage(null)}
          type="success"
        />
      )}
    </div>
  );
};
