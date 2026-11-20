import React, { useState } from 'react';
import { Video, FileText, Clock, Loader2, AlertCircle } from 'lucide-react';
import { MeetingDetail } from '../../types/meeting';
import { MeetingHeader } from './MeetingHeader';
import { OverviewCard } from './OverviewCard';
import { KeyPointsCard } from './KeyPointsCard';
import { VideoPlayer } from './VideoPlayer';
import { SpeakersCard } from './SpeakersCard';
import { TranscriptCard } from './TranscriptCard';

interface MeetingDetailsViewProps {
  meeting?: MeetingDetail | null;
  onBack?: () => void;
  onToggleActionItem?: (id: string) => void;
}

export const MeetingDetailsView: React.FC<MeetingDetailsViewProps> = ({
  meeting,
  onBack,
  onToggleActionItem,
}) => {
  const [activeTab, setActiveTab] = useState<'summary' | 'transcript'>('summary');
  const [seekTime, setSeekTime] = useState<number | null>(null);
  const [seekTarget, setSeekTarget] = useState<{ time: number; id: number } | null>(null);

  const handleSeek = (seconds: number) => {
    setSeekTime(seconds);
    setSeekTarget({ time: seconds, id: Date.now() });
  };

  if (!meeting) {
    return (
      <div className="bg-white rounded-2xl p-12 text-center border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-2">
        <div className="w-8 h-8 rounded-full bg-[#f4f0ff] flex items-center justify-center text-[#5932ea] mx-auto mb-2">
          <Video className="w-4 h-4 text-[#5932ea]" />
        </div>
        <h3 className="text-sm font-bold text-[#141522]">No Meeting Selected</h3>
        <p className="text-xs text-gray-500 max-w-sm mx-auto">
          Select a meeting from the recent meetings list or join a new meeting to view summary details.
        </p>
      </div>
    );
  }

  // Non-completed states: 'scheduled', 'processing', 'failed'
  // Show the player whenever a media URL exists, even while the status is 'scheduled' or 'processing'.
  // Summary, Transcript, and Key Points stay hidden until 'completed'.
  if (meeting.status !== 'completed') {
    const renderStatusCard = () => {
      if (meeting.status === 'scheduled') {
        return (
          <div className="bg-white rounded-2xl p-10 text-center border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-[#f4f0ff] text-[#5932ea] flex items-center justify-center mx-auto mb-2">
              <Clock className="w-6 h-6 animate-pulse" />
            </div>
            <h2 className="text-base font-bold text-[#141522]">Waiting to be processed</h2>
            <p className="text-xs text-gray-500 max-w-md mx-auto">
              This meeting is scheduled and will be processed shortly. Updates will appear automatically.
            </p>
          </div>
        );
      }

      if (meeting.status === 'processing') {
        const processed = meeting.processedSeconds;
        const duration = meeting.durationSeconds;
        let processingLabel = 'Processing…';
        if (processed != null && duration != null && duration > 0) {
          const currentMin = Math.ceil(processed / 60);
          const totalMin = Math.ceil(duration / 60);
          processingLabel = `Processing: ${currentMin} of ${totalMin} min`;
        }

        return (
          <div className="bg-white rounded-2xl p-10 text-center border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-2">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
            <h2 className="text-base font-bold text-[#141522]">{processingLabel}</h2>
            <p className="text-xs text-gray-500 max-w-md mx-auto">
              Generating summary, transcript, and diarization. The details will load when complete.
            </p>
          </div>
        );
      }

      if (meeting.status === 'failed') {
        return (
          <div className="bg-white rounded-2xl p-10 text-center border border-rose-200 bg-rose-50/20 shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto mb-2">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-rose-900">Meeting Processing Failed</h2>
            {meeting.error && (
              <p className="text-xs text-rose-600 max-w-md mx-auto">
                {meeting.error}
              </p>
            )}
          </div>
        );
      }

      return null;
    };

    return (
      <div className="space-y-4">
        {/* Header (Title, Folder, Date, Time range, Share, Export) */}
        <MeetingHeader meeting={meeting} onBack={onBack} />

        {meeting.mediaUrl ? (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
            {/* Status card in left column */}
            <div className="xl:col-span-7">
              {renderStatusCard()}
            </div>

            {/* Video / Audio Player in right column */}
            <div className="xl:col-span-5 space-y-4">
              <VideoPlayer
                mediaUrl={meeting.mediaUrl}
                mediaType={meeting.mediaType}
                durationSeconds={meeting.durationSeconds}
                speakers={meeting.speakers || []}
                transcript={meeting.transcript || []}
                seekTime={seekTime}
                seekTarget={seekTarget}
                onSeek={handleSeek}
              />
              {meeting.speakers && meeting.speakers.length > 0 && (
                <SpeakersCard speakers={meeting.speakers} />
              )}
            </div>
          </div>
        ) : (
          renderStatusCard()
        )}
      </div>
    );
  }

  // 4. Status: 'completed' -> normal page with Summary, Transcript, Key Points, Player, Speakers
  const hasSummary = Boolean(meeting.summary);

  return (
    <div className="space-y-4">
      {/* 1. Header (Title, Folder, Date, Time range, Share, Export, More) */}
      <MeetingHeader meeting={meeting} onBack={onBack} />

      {/* 2. Main Tabs: Summary / Transcript */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setActiveTab('summary')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
            activeTab === 'summary'
              ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
              : 'bg-white text-gray-700 border border-gray-200 hover:border-gray-300'
          }`}
        >
          <Video className="w-4 h-4 text-[#5932ea]" />
          <span>Summary</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('transcript')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
            activeTab === 'transcript'
              ? 'bg-[#f4f0ff] text-[#5932ea] border border-[#e2d8fe]'
              : 'bg-white text-gray-700 border border-gray-200 hover:border-gray-300'
          }`}
        >
          <FileText className="w-4 h-4 text-gray-500" />
          <span>Transcript</span>
        </button>
      </div>

      {/* 3. Sub-split: Left (Overview + Key points or Transcript) & Right (Video player + Speakers) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
        {/* Left Sub-column (~58% / 7 cols) */}
        <div className="xl:col-span-7 space-y-4">
          {activeTab === 'summary' ? (
            hasSummary ? (
              <>
                {/* Overview Card */}
                <OverviewCard overview={meeting.summary?.overview} />

                {/* Key points Card (4 Quadrants) */}
                <KeyPointsCard
                  summary={meeting.summary}
                  meetingId={meeting.id}
                  onToggleActionItem={onToggleActionItem}
                />
              </>
            ) : (
              <div className="bg-white rounded-2xl p-8 text-center border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] space-y-2">
                <div className="w-8 h-8 rounded-full bg-[#f4f0ff] flex items-center justify-center text-[#5932ea] mx-auto mb-2">
                  <FileText className="w-4 h-4 text-[#5932ea]" />
                </div>
                <h3 className="text-sm font-bold text-[#141522]">Summary not available</h3>
                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                  The AI summary for this meeting is currently being generated or is not yet available.
                </p>
              </div>
            )
          ) : (
            <TranscriptCard
              transcript={meeting.transcript || []}
              onSeek={handleSeek}
            />
          )}
        </div>

        {/* Right Sub-column (~42% / 5 cols) */}
        <div className="xl:col-span-5 space-y-4">
          {/* Video / Audio Player Card */}
          <VideoPlayer
            mediaUrl={meeting.mediaUrl}
            mediaType={meeting.mediaType}
            durationSeconds={meeting.durationSeconds}
            speakers={meeting.speakers || []}
            transcript={meeting.transcript || []}
            seekTime={seekTime}
            seekTarget={seekTarget}
            onSeek={handleSeek}
          />

          {/* Speakers Card */}
          <SpeakersCard
            speakers={meeting.speakers || []}
          />
        </div>
      </div>
    </div>
  );
};
