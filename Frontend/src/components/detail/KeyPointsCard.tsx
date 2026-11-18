import React, { useState } from 'react';
import { Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import { MeetingSummary, ProgressItem, ChallengeItem, ActionItem } from '../../types/meeting';

interface KeyPointsCardProps {
  summary?: MeetingSummary | null;
}

export const KeyPointsCard: React.FC<KeyPointsCardProps> = ({ summary }) => {
  const [isOpen, setIsOpen] = useState(true);

  // Normalize string or object items
  const formatBullet = (item: string | ProgressItem | ChallengeItem | ActionItem): string => {
    if (!item) return '';
    if (typeof item === 'string') return item;
    if ('task' in item && item.task) return item.task;
    if ('title' in item && item.title) return item.title;
    return String(item);
  };

  // Safely extract from both camelCase and snake_case or nested key_points
  const rawProgress =
    summary?.projectProgress ||
    summary?.project_progress ||
    summary?.key_points?.project_progress ||
    [];

  const rawChallenges =
    summary?.challengesFaced ||
    summary?.challenges_faced ||
    summary?.challenge_faced ||
    summary?.key_points?.challenges_faced ||
    summary?.key_points?.challenge_faced ||
    [];

  const rawActions =
    summary?.actionItems ||
    summary?.action_items ||
    summary?.key_points?.action_items ||
    [];

  const rawNextSteps =
    summary?.nextSteps ||
    summary?.next_steps ||
    summary?.key_points?.next_steps ||
    [];

  const progressBullets = Array.isArray(rawProgress)
    ? rawProgress.map(formatBullet).filter(Boolean)
    : [];
  const challengesBullets = Array.isArray(rawChallenges)
    ? rawChallenges.map(formatBullet).filter(Boolean)
    : [];
  const actionItemsBullets = Array.isArray(rawActions)
    ? rawActions.map(formatBullet).filter(Boolean)
    : [];
  const nextStepsBullets = Array.isArray(rawNextSteps)
    ? rawNextSteps.map((s) => (typeof s === 'string' ? s : String(s))).filter(Boolean)
    : [];

  const hasAnyKeyPoints =
    progressBullets.length > 0 ||
    challengesBullets.length > 0 ||
    actionItemsBullets.length > 0 ||
    nextStepsBullets.length > 0;

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between cursor-pointer select-none mb-3"
      >
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-purple-600" />
          <h2 className="text-sm font-bold text-[#141522] tracking-tight">Key points</h2>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </div>

      {/* 2x2 Quadrant Grid */}
      {isOpen && (
        hasAnyKeyPoints ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
            {/* Quadrant 1: Project Progress */}
            <div className="border border-gray-200/90 rounded-xl p-3.5 bg-white">
              <h3 className="text-xs font-bold text-[#141522] mb-2.5">Project Progress</h3>
              {progressBullets.length > 0 ? (
                <ul className="space-y-2">
                  {progressBullets.map((bullet, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-gray-600 leading-snug">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#5932ea] shrink-0 mt-1" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400 italic">No progress updates recorded.</p>
              )}
            </div>

            {/* Quadrant 2: Challenge Faced */}
            <div className="border border-gray-200/90 rounded-xl p-3.5 bg-white">
              <h3 className="text-xs font-bold text-[#141522] mb-2.5">Challenge Faced</h3>
              {challengesBullets.length > 0 ? (
                <ul className="space-y-2">
                  {challengesBullets.map((bullet, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-gray-600 leading-snug">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#5932ea] shrink-0 mt-1" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400 italic">No challenges reported.</p>
              )}
            </div>

            {/* Quadrant 3: Action Items */}
            <div className="border border-gray-200/90 rounded-xl p-3.5 bg-white">
              <h3 className="text-xs font-bold text-[#141522] mb-2.5">Action Items</h3>
              {actionItemsBullets.length > 0 ? (
                <ul className="space-y-2">
                  {actionItemsBullets.map((bullet, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-gray-600 leading-snug">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#5932ea] shrink-0 mt-1" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400 italic">No action items assigned.</p>
              )}
            </div>

            {/* Quadrant 4: Next Steps */}
            <div className="border border-gray-200/90 rounded-xl p-3.5 bg-white">
              <h3 className="text-xs font-bold text-[#141522] mb-2.5">Next Steps</h3>
              {nextStepsBullets.length > 0 ? (
                <ul className="space-y-2">
                  {nextStepsBullets.map((bullet, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-gray-600 leading-snug">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#5932ea] shrink-0 mt-1" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400 italic">No next steps defined.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="py-6 text-center text-xs text-gray-400">
            No key points available for this meeting.
          </div>
        )
      )}
    </div>
  );
};
