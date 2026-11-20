import React from 'react';
import { MessageSquare } from 'lucide-react';
import { Speaker } from '../../types/meeting';
import { formatSecondsToTime } from '../../utils/formatters';

interface SpeakersTabProps {
  speakers: Speaker[];
  onSelectSpeaker?: (speaker: Speaker) => void;
}

export const SpeakersTab: React.FC<SpeakersTabProps> = ({ speakers }) => {
  return (
    <div className="space-y-3">
      {speakers.map((spk) => (
        <div
          key={spk.id}
          className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs hover:border-slate-300 transition-all"
        >
          <div className="flex items-center justify-between gap-3 mb-2.5">
            <div className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-2xs"
                style={{ backgroundColor: spk.color }}
              >
                {spk.name.charAt(0)}
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">{spk.name}</h4>
                <p className="text-[11px] text-slate-400">{spk.role}</p>
              </div>
            </div>

            <span className="text-xs font-bold text-indigo-600 font-mono">
              {spk.talkPercentage}% talk
            </span>
          </div>

          {/* Talk percentage visual bar */}
          <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mb-3">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${spk.talkPercentage}%`,
                backgroundColor: spk.color,
              }}
            />
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
            <div className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3 text-slate-400" />
              <span>{formatSecondsToTime(spk.talkDurationSeconds || 0)}</span>
            </div>
            {spk.listenPercentage != null && (
              <div className="flex items-center gap-1">
                <span>Listen: {spk.listenPercentage}%</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
