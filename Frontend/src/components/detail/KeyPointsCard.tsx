import React, { useState } from 'react';
import { Calendar, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { MeetingSummary, ProgressItem, ChallengeItem, ActionItem } from '../../types/meeting';
import { Toast } from '../common/Toast';
import { updateActionItem } from '../../services/meetingService';

interface KeyPointsCardProps {
  summary?: MeetingSummary | null;
  meetingId?: string;
  onToggleActionItem?: (id: string) => void | Promise<void>;
}

export const KeyPointsCard: React.FC<KeyPointsCardProps> = ({
  summary,
  meetingId,
  onToggleActionItem,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [localDoneState, setLocalDoneState] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

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
  const actionItemsList: ActionItem[] = Array.isArray(rawActions)
    ? rawActions.map((item, idx) => {
        if (typeof item === 'string') {
          return { id: `ai-${idx}`, task: item, done: false, completed: false };
        }
        return {
          ...item,
          id: item.id || `ai-${idx}`,
          done: item.done ?? item.completed ?? false,
        };
      })
    : [];
  const nextStepsBullets = Array.isArray(rawNextSteps)
    ? rawNextSteps.map((s) => (typeof s === 'string' ? s : String(s))).filter(Boolean)
    : [];

  const hasAnyKeyPoints =
    progressBullets.length > 0 ||
    challengesBullets.length > 0 ||
    actionItemsList.length > 0 ||
    nextStepsBullets.length > 0;

  const handleActionItemClick = async (itemId?: string) => {
    if (!itemId) return;
    if (onToggleActionItem) {
      onToggleActionItem(itemId);
      return;
    }
    if (!meetingId) return;

    const item = actionItemsList.find((it) => it.id === itemId);
    const prevDone = localDoneState[itemId] ?? Boolean(item?.done ?? item?.completed);
    const nextDone = !prevDone;

    // Tick immediately
    setLocalDoneState((prev) => ({ ...prev, [itemId]: nextDone }));

    try {
      await updateActionItem(meetingId, itemId, { done: nextDone });
    } catch (err: unknown) {
      // Revert & show toast on failure
      setLocalDoneState((prev) => ({ ...prev, [itemId]: prevDone }));
      setToastMessage((err as Error)?.message || 'Failed to update action item.');
    }
  };

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
              {actionItemsList.length > 0 ? (
                <ul className="space-y-2">
                  {actionItemsList.map((item, idx) => {
                    const isDone = localDoneState[item.id!] ?? Boolean(item.done ?? item.completed);
                    return (
                      <li
                        key={item.id || idx}
                        onClick={() => handleActionItemClick(item.id)}
                        className="flex items-start gap-2 text-xs text-gray-600 leading-snug cursor-pointer group select-none"
                      >
                        <button
                          type="button"
                          className={`w-3.5 h-3.5 rounded flex items-center justify-center shrink-0 mt-0.5 transition-colors cursor-pointer ${
                            isDone
                              ? 'bg-[#5932ea] text-white border border-[#5932ea]'
                              : 'border border-gray-300 group-hover:border-[#5932ea]'
                          }`}
                          aria-label={isDone ? 'Mark incomplete' : 'Mark complete'}
                        >
                          {isDone && <Check className="w-2.5 h-2.5 stroke-3" />}
                        </button>
                        <span className={isDone ? 'line-through text-gray-400' : 'text-gray-600'}>
                          {item.task}
                        </span>
                      </li>
                    );
                  })}
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

      {/* Standalone Error Toast */}
      {toastMessage && (
        <Toast
          isOpen={!!toastMessage}
          message={toastMessage}
          onClose={() => setToastMessage(null)}
          type="error"
        />
      )}
    </div>
  );
};
