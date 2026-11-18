import React, { useState } from 'react';
import { Video, FileText } from 'lucide-react';
import { Speaker, Topic } from '../../types/meeting';

interface SpeakersCardProps {
  speakers?: Speaker[];
  topics?: Topic[];
  onSeekTopic?: (seconds: number) => void;
}

export const SpeakersCard: React.FC<SpeakersCardProps> = ({
  speakers = [],
  topics = [],
  onSeekTopic,
}) => {
  const [activeTab, setActiveTab] = useState<'speakers' | 'topics'>('speakers');

  const safeSpeakers = speakers || [];
  const safeTopics = topics || [];

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-4">
      {/* Tabs */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setActiveTab('speakers')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'speakers'
              ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
              : 'text-gray-500 hover:text-gray-900 border border-transparent'
          }`}
        >
          <Video className="w-3.5 h-3.5 text-[#5932ea]" />
          <span>Speakers</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('topics')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'topics'
              ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
              : 'text-gray-500 hover:text-gray-900 border border-transparent'
          }`}
        >
          <FileText className="w-3.5 h-3.5 text-gray-500" />
          <span>Topics</span>
        </button>
      </div>

      {activeTab === 'speakers' ? (
        /* Speakers Table */
        <div className="overflow-x-auto">
          {safeSpeakers.length > 0 ? (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[11px] font-medium text-gray-400 border-b border-gray-100 pb-2">
                  <th className="pb-2 font-medium">Participants</th>
                  <th className="pb-2 font-medium text-center">Talk Time</th>
                  <th className="pb-2 font-medium text-center">Task Time</th>
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
                        <img
                          src={spk.avatar || 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80'}
                          alt={spk.name}
                          className="w-7 h-7 rounded-full object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <p className="font-bold text-xs text-[#141522] truncate leading-tight">
                            {spk.name}
                          </p>
                          <p className="text-[10px] text-gray-400 truncate leading-tight">
                            {spk.role}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Talk Time */}
                    <td className="py-2.5 text-center text-xs text-[#141522] font-medium">
                      {spk.talkDurationLabel || '1h'}
                    </td>

                    {/* Task Time */}
                    <td className="py-2.5 text-center text-xs text-[#141522] font-medium">
                      {spk.taskTimeLabel || '25m'}
                    </td>

                    {/* Talk % with Mini Progress Bar */}
                    <td className="py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <span className="text-xs text-[#141522] font-medium">{spk.talkPercentage}%</span>
                        <div className="w-8 h-1 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#5932ea] rounded-full"
                            style={{ width: `${Math.min(100, spk.talkPercentage * 1.5)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Listen % */}
                    <td className="py-2.5 text-center text-xs text-[#141522] font-medium">
                      {spk.listenPercentage || 70}%
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
      ) : (
        /* Topics View */
        <div className="space-y-3">
          {safeTopics.length > 0 ? (
            safeTopics.map((topic, idx) => (
              <div
                key={topic.id}
                onClick={() => onSeekTopic && onSeekTopic(topic.timestampStart)}
                className="p-3 rounded-xl border border-gray-100 hover:border-[#5932ea] transition-all cursor-pointer bg-gray-50/40"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-bold text-[#141522]">
                    {idx + 1}. {topic.name}
                  </span>
                  <span className="text-[10px] text-[#5932ea] font-semibold bg-[#f0edff] px-2 py-0.5 rounded">
                    Relevance {topic.relevanceScore || 90}%
                  </span>
                </div>
                {topic.keyPoints && topic.keyPoints.length > 0 && (
                  <ul className="text-xs text-gray-500 space-y-0.5 pl-3 list-disc">
                    {topic.keyPoints.map((kp, kIdx) => (
                      <li key={kIdx}>{kp}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))
          ) : (
            <div className="py-8 text-center text-xs text-gray-400">
              No topic segments recorded for this meeting.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
