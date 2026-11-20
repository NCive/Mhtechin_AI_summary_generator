import React from 'react';
import { Video } from 'lucide-react';
import { Speaker } from '../../types/meeting';

interface SpeakersCardProps {
  speakers?: Speaker[];
}

export const SpeakersCard: React.FC<SpeakersCardProps> = ({
  speakers = [],
}) => {
  const safeSpeakers = speakers || [];

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Video className="w-4 h-4 text-[#5932ea]" />
        <h3 className="text-sm font-bold text-[#141522]">Speakers</h3>
      </div>

      {/* Speakers Table */}
      <div className="overflow-x-auto">
        {safeSpeakers.length > 0 ? (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[11px] font-medium text-gray-400 border-b border-gray-100 pb-2">
                <th className="pb-2 font-medium">Participants</th>
                <th className="pb-2 font-medium text-center">Talk Time</th>
                <th className="pb-2 font-medium text-center">Talk %</th>
                <th className="pb-2 font-medium text-center">Listen %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {safeSpeakers.map((spk) => (
                <tr key={spk.id} className="hover:bg-gray-50/50 transition-colors">
                  {/* Participant Avatar & Name */}
                  <td className="py-2.5 pr-2">
                    <div className="flex items-center gap-2">
                      {spk.avatar ? (
                        <img
                          src={spk.avatar}
                          alt={spk.name}
                          className="w-7 h-7 rounded-full object-cover shrink-0"
                        />
                      ) : (
                        <div
                          className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                          style={{ backgroundColor: spk.color || '#5932ea' }}
                        >
                          {spk.name?.charAt(0) || '?'}
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="font-bold text-xs text-[#141522] truncate leading-tight">
                          {spk.name}
                        </p>
                        {spk.role && (
                          <p className="text-[10px] text-gray-400 truncate leading-tight">
                            {spk.role}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Talk Time */}
                  <td className="py-2.5 text-center text-xs text-[#141522] font-medium">
                    {spk.talkDurationLabel || (spk.talkDurationSeconds ? `${Math.round(spk.talkDurationSeconds / 60)}m` : '—')}
                  </td>

                  {/* Talk % with Mini Progress Bar */}
                  <td className="py-2.5 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <span className="text-xs text-[#141522] font-medium">
                        {spk.talkPercentage != null ? `${spk.talkPercentage}%` : '—'}
                      </span>
                      {spk.talkPercentage != null && (
                        <div className="w-8 h-1 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#5932ea] rounded-full"
                            style={{ width: `${Math.min(100, spk.talkPercentage * 1.5)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Listen % */}
                  <td className="py-2.5 text-center text-xs text-[#141522] font-medium">
                    {spk.listenPercentage != null ? `${spk.listenPercentage}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-8 text-center text-xs text-gray-400">
            No speaker data available for this meeting.
          </div>
        )}
      </div>
    </div>
  );
};
