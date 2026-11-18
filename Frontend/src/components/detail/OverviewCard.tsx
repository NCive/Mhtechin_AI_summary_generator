import React, { useState } from 'react';
import { Calendar, ChevronDown, ChevronUp } from 'lucide-react';

interface OverviewCardProps {
  overview?: string | null;
}

export const OverviewCard: React.FC<OverviewCardProps> = ({ overview }) => {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between cursor-pointer select-none"
      >
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-purple-600" />
          <h2 className="text-sm font-bold text-[#141522] tracking-tight">Overview</h2>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </div>

      {/* Body */}
      {isOpen && (
        <p className="mt-3 text-xs text-gray-600 leading-relaxed">
          {overview || 'No overview provided for this meeting.'}
        </p>
      )}
    </div>
  );
};
