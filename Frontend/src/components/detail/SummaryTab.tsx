import React, { useState } from 'react';
import {
  FileText,
  TrendingUp,
  AlertTriangle,
  CheckSquare,
  ArrowRightCircle,
  Calendar,
  Check,
} from 'lucide-react';
import { MeetingSummary, ProgressItem, ChallengeItem, ActionItem } from '../../types/meeting';
import { Toast } from '../common/Toast';
import { formatSimpleDate } from '../../utils/formatters';
import { updateActionItem } from '../../services/meetingService';

interface SummaryTabProps {
  summary?: MeetingSummary | null;
  meetingId?: string;
  onToggleActionItem?: (id: string) => void | Promise<void>;
}

export const SummaryTab: React.FC<SummaryTabProps> = ({
  summary,
  meetingId,
  onToggleActionItem,
}) => {
  const [localDoneState, setLocalDoneState] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  if (!summary) {
    return (
      <div className="bg-white rounded-xl border border-slate-200/90 p-8 text-center text-xs text-slate-400">
        No summary notes available for this meeting.
      </div>
    );
  }

  const rawProgress = summary.projectProgress || summary.project_progress || summary.key_points?.project_progress || [];
  const rawChallenges = summary.challengesFaced || summary.challenges_faced || summary.challenge_faced || summary.key_points?.challenges_faced || [];
  const rawActions = summary.actionItems || summary.action_items || summary.key_points?.action_items || [];
  const rawNext = summary.nextSteps || summary.next_steps || summary.key_points?.next_steps || [];

  const progressList: ProgressItem[] = Array.isArray(rawProgress)
    ? rawProgress.map((item, idx) =>
        typeof item === 'string'
          ? { id: `prog-${idx}`, title: item, status: 'completed' as const }
          : item
      )
    : [];

  const challengesList: ChallengeItem[] = Array.isArray(rawChallenges)
    ? rawChallenges.map((item, idx) =>
        typeof item === 'string'
          ? { id: `chal-${idx}`, title: item, severity: 'medium' as const }
          : item
      )
    : [];

  const actionList: ActionItem[] = Array.isArray(rawActions)
    ? rawActions.map((item, idx) =>
        typeof item === 'string'
          ? { id: `act-${idx}`, task: item, completed: false, done: false }
          : { ...item, id: item.id || `act-${idx}`, done: item.done ?? item.completed ?? false }
      )
    : [];

  const handleToggle = async (itemId?: string) => {
    if (!itemId) return;
    if (onToggleActionItem) {
      onToggleActionItem(itemId);
      return;
    }
    if (!meetingId) return;

    const item = actionList.find((it) => it.id === itemId);
    const prevDone = localDoneState[itemId] ?? Boolean(item?.done ?? item?.completed);
    const nextDone = !prevDone;

    // Tick immediately
    setLocalDoneState((prev) => ({ ...prev, [itemId]: nextDone }));

    try {
      await updateActionItem(meetingId, itemId, { done: nextDone });
    } catch (err: unknown) {
      // Revert & toast
      setLocalDoneState((prev) => ({ ...prev, [itemId]: prevDone }));
      setToastMessage((err as Error)?.message || 'Failed to update action item.');
    }
  };

  const nextList: string[] = Array.isArray(rawNext)
    ? rawNext.map((item) => (typeof item === 'string' ? item : String(item)))
    : [];

  return (
    <div className="space-y-6">
      {/* 1. Overview */}
      <section className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Executive Overview
          </h3>
        </div>
        <p className="text-sm text-slate-700 leading-relaxed font-normal">
          {summary.overview || 'No overview generated for this session.'}
        </p>
      </section>

      {/* 2. Project Progress */}
      <section className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-emerald-600" />
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Project Progress & Milestones
          </h3>
        </div>
        {progressList.length > 0 ? (
          <div className="space-y-3">
            {progressList.map((item) => (
              <div
                key={item.id || item.title}
                className="p-3 rounded-lg bg-slate-50 border border-slate-200/70"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">{item.title}</span>
                  </div>
                  {item.notes && <p className="text-xs text-slate-600">{item.notes}</p>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">No project progress updates captured.</p>
        )}
      </section>

      {/* 3. Challenges Faced */}
      <section className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Challenges Faced & Risks
          </h3>
        </div>
        {challengesList.length > 0 ? (
          <div className="space-y-3">
            {challengesList.map((item) => (
              <div
                key={item.id || item.title}
                className="p-3.5 rounded-lg bg-amber-50/40 border border-amber-200/70"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <h4 className="text-sm font-semibold text-amber-950">{item.title}</h4>
                </div>
                {item.description && (
                  <p className="text-xs text-slate-700 leading-relaxed">{item.description}</p>
                )}
                {item.impact && (
                  <div className="mt-2 text-[11px] font-medium text-amber-800 bg-amber-100/60 px-2 py-1 rounded inline-block">
                    Impact: {item.impact}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">No significant challenges recorded in this meeting.</p>
        )}
      </section>

      {/* 4. Action Items */}
      <section className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Action Items & Assignments
            </h3>
          </div>
          {actionList.length > 0 && (
            <span className="text-xs text-slate-500 font-medium">
              {actionList.filter((a) => Boolean(localDoneState[a.id!] ?? (a.done ?? a.completed))).length} / {actionList.length} Done
            </span>
          )}
        </div>

        {actionList.length > 0 ? (
          <div className="space-y-2.5">
            {actionList.map((item) => {
              const isDone = Boolean(localDoneState[item.id!] ?? (item.done ?? item.completed));
              return (
                <div
                  key={item.id || item.task}
                  onClick={() => item.id && handleToggle(item.id)}
                  className={`flex items-start gap-3 p-3 rounded-lg border transition-all cursor-pointer ${
                    isDone
                      ? 'bg-slate-50 border-slate-200 text-slate-400'
                      : 'bg-white border-slate-200 hover:border-indigo-300 shadow-2xs'
                  }`}
                >
                  <button
                    type="button"
                    className={`mt-0.5 w-4 h-4 rounded flex items-center justify-center transition-colors shrink-0 ${
                      isDone ? 'bg-emerald-600 text-white' : 'border border-slate-300 hover:border-indigo-500'
                    }`}
                    aria-label={isDone ? 'Mark incomplete' : 'Mark complete'}
                  >
                    {isDone && <Check className="w-3 h-3 stroke-3" />}
                  </button>

                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium leading-snug ${
                        isDone ? 'line-through text-slate-400' : 'text-slate-800'
                      }`}
                    >
                    {item.task}
                  </p>

                  <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-slate-500">
                    {item.assignee && (
                      <span className="font-semibold text-slate-700">Assignee: {item.assignee}</span>
                    )}
                    {item.dueDate && (
                      <span className="flex items-center gap-1 text-slate-500">
                        <Calendar className="w-3 h-3" />
                        Due: {formatSimpleDate(item.dueDate)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">No action items defined.</p>
        )}
      </section>

      {/* 5. Next Steps */}
      <section className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs">
        <div className="flex items-center gap-2 mb-3">
          <ArrowRightCircle className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Next Steps & Strategy
          </h3>
        </div>
        {nextList.length > 0 ? (
          <ul className="space-y-2">
            {nextList.map((step, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-sm text-slate-700">
                <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-500 italic">No next steps documented.</p>
        )}
      </section>

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
