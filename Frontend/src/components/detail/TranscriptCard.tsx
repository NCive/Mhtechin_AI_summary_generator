import React, { useState } from 'react';
import { Search, Play } from 'lucide-react';
import { TranscriptUtterance } from '../../types/meeting';
import { formatSecondsToTime } from '../../utils/formatters';

interface TranscriptCardProps {
  transcript: TranscriptUtterance[];
  onSeek?: (seconds: number) => void;
}

export const TranscriptCard: React.FC<TranscriptCardProps> = ({
  transcript,
  onSeek,
}) => {
  const [query, setQuery] = useState('');

  const filtered = transcript.filter(
    (t) =>
      (t.text ?? '').toLowerCase().includes(query.toLowerCase()) ||
      (t.speakerName ?? '').toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
      {/* Header & Search */}
      <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-3">
        <h3 className="text-sm font-bold text-[#141522]">Meeting Transcript</h3>
        <div className="relative w-48 sm:w-64">
          <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-lg text-[#141522] placeholder:text-gray-400 focus:outline-none focus:border-[#5932ea]"
          />
        </div>
      </div>

      {/* Utterance list */}
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="p-3 rounded-xl border border-gray-100 bg-gray-50/30 hover:border-gray-200 transition-colors"
          >
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: item.speakerColor || '#94a3b8' }}
                />
                <span className="text-xs font-bold text-[#141522]">{item.speakerName || 'Unknown speaker'}</span>
              </div>
              <button
                type="button"
                onClick={() => onSeek && onSeek(item.timestampStart ?? 0)}
                className="flex items-center gap-1 text-[11px] font-mono text-[#5932ea] hover:underline cursor-pointer"
              >
                <Play className="w-2.5 h-2.5 fill-current" />
                <span>{formatSecondsToTime(item.timestampStart ?? 0)}</span>
              </button>
            </div>
            <p className="text-xs text-gray-600 leading-relaxed pl-4 border-l-2 border-gray-200">
              {item.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
