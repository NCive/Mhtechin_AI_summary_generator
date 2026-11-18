import React from 'react';
import { Clock } from 'lucide-react';
import { Topic } from '../../types/meeting';
import { formatSecondsToTime, formatDurationLabel } from '../../utils/formatters';

interface TopicsTabProps {
  topics: Topic[];
  onSeek?: (seconds: number) => void;
}

export const TopicsTab: React.FC<TopicsTabProps> = ({ topics, onSeek }) => {
  return (
    <div className="space-y-3">
      {topics.map((top, idx) => (
        <div
          key={top.id}
          className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs hover:border-indigo-300 transition-all"
        >
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-md bg-indigo-50 text-indigo-600 text-[11px] font-bold flex items-center justify-center shrink-0">
                {idx + 1}
              </span>
              <h4 className="text-xs font-bold text-slate-900">{top.name}</h4>
            </div>

            {onSeek && (
              <button
                onClick={() => onSeek(top.timestampStart)}
                className="text-[11px] font-mono text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded font-medium flex items-center gap-1"
                title="Jump to topic start"
              >
                <Clock className="w-2.5 h-2.5" />
                <span>{formatSecondsToTime(top.timestampStart)}</span>
              </button>
            )}
          </div>

          <div className="text-[11px] text-slate-400 mb-2.5">
            Duration: {formatDurationLabel(top.durationSeconds)} • Relevance {top.relevanceScore || 90}%
          </div>

          {top.keyPoints && top.keyPoints.length > 0 && (
            <ul className="space-y-1.5 text-xs text-slate-600 pl-2 border-l-2 border-indigo-100">
              {top.keyPoints.map((kp, kIdx) => (
                <li key={kIdx} className="leading-relaxed flex items-start gap-1.5">
                  <span className="text-indigo-400 mt-1">•</span>
                  <span>{kp}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
};
