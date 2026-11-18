import React from 'react';
import {
  Activity,
  Smile,
  Users,
  HelpCircle,
  Gauge,
  Clock,
} from 'lucide-react';
import { ParticipantAnalytics as AnalyticsType } from '../../types/meeting';
import { formatDurationLabel, formatSecondsToTime } from '../../utils/formatters';

interface ParticipantAnalyticsProps {
  analytics: AnalyticsType;
}

export const ParticipantAnalytics: React.FC<ParticipantAnalyticsProps> = ({ analytics }) => {
  const {
    totalDurationSeconds,
    overallSentiment,
    totalSpeakers,
    questionsAskedCount,
    averagePaceWpm,
    engagementScore,
    speakerTalkTimeDistribution,
  } = analytics;

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Participant Analytics & Engagement
          </h3>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700">
          Engagement: {engagementScore}%
        </span>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Duration</span>
          </div>
          <p className="text-base font-bold text-slate-800">
            {formatDurationLabel(totalDurationSeconds)}
          </p>
        </div>

        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <Users className="w-3.5 h-3.5" />
            <span>Speakers</span>
          </div>
          <p className="text-base font-bold text-slate-800">{totalSpeakers}</p>
        </div>

        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Questions</span>
          </div>
          <p className="text-base font-bold text-slate-800">{questionsAskedCount}</p>
        </div>

        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <Gauge className="w-3.5 h-3.5" />
            <span>Avg Pace</span>
          </div>
          <p className="text-base font-bold text-slate-800">{averagePaceWpm} wpm</p>
        </div>
      </div>

      {/* Sentiment Breakdown */}
      <div>
        <div className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1.5">
          <div className="flex items-center gap-1.5">
            <Smile className="w-3.5 h-3.5 text-emerald-600" />
            <span>Sentiment Breakdown</span>
          </div>
          <div className="flex items-center gap-3 text-[11px]">
            <span className="text-emerald-600">Positive: {overallSentiment.positive}%</span>
            <span className="text-slate-500">Neutral: {overallSentiment.neutral}%</span>
            <span className="text-rose-500">Concerns: {overallSentiment.negative}%</span>
          </div>
        </div>

        {/* Stacked bar */}
        <div className="w-full h-2.5 rounded-full bg-slate-100 flex overflow-hidden">
          <div
            style={{ width: `${overallSentiment.positive}%` }}
            className="bg-emerald-500 h-full transition-all"
            title={`Positive: ${overallSentiment.positive}%`}
          />
          <div
            style={{ width: `${overallSentiment.neutral}%` }}
            className="bg-slate-300 h-full transition-all"
            title={`Neutral: ${overallSentiment.neutral}%`}
          />
          <div
            style={{ width: `${overallSentiment.negative}%` }}
            className="bg-rose-500 h-full transition-all"
            title={`Concerns: ${overallSentiment.negative}%`}
          />
        </div>
      </div>

      {/* Speaker Talk Time Distribution */}
      <div>
        <h4 className="text-xs font-semibold text-slate-700 mb-2">
          Talk Time Share
        </h4>
        <div className="space-y-2">
          {speakerTalkTimeDistribution.map((item, idx) => (
            <div key={idx} className="space-y-1">
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span className="font-medium text-slate-800">{item.speakerName}</span>
                <span className="font-mono text-slate-500">
                  {formatSecondsToTime(item.durationSeconds)} ({item.percentage}%)
                </span>
              </div>
              <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${item.percentage}%`,
                    backgroundColor: item.color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
