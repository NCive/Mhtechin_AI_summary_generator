import React from 'react';
import { TranscriptUtterance, Speaker } from '../../types/meeting';
import { formatSecondsToTime } from '../../utils/formatters';

interface SpeakerTimelineProps {
  durationSeconds: number;
  currentTime: number;
  transcript: TranscriptUtterance[];
  speakers: Speaker[];
  onSeek: (seconds: number) => void;
}

export const SpeakerTimeline: React.FC<SpeakerTimelineProps> = ({
  durationSeconds,
  currentTime,
  transcript,
  speakers,
  onSeek,
}) => {
  const total = Math.max(durationSeconds, 1);

  // Map speaker colors
  const speakerColorMap = speakers.reduce((acc, spk) => {
    acc[spk.id] = spk.color;
    acc[spk.name] = spk.color;
    return acc;
  }, {} as Record<string, string>);

  const handleBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(ratio * total);
  };

  const progressPercent = Math.min(100, (currentTime / total) * 100);

  return (
    <div className="w-full mt-3">
      <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 mb-1.5">
        <span className="flex items-center gap-1.5 uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-indigo-500" />
          Speaker Timeline
        </span>
        <span className="text-slate-400">
          {formatSecondsToTime(currentTime)} / {formatSecondsToTime(total)}
        </span>
      </div>

      {/* Interactive timeline bar */}
      <div
        onClick={handleBarClick}
        className="relative h-7 w-full bg-slate-200 rounded-lg overflow-hidden cursor-pointer select-none border border-slate-300 shadow-inner group"
        title="Click anywhere to jump to timestamp"
      >
        {/* Utterance segments */}
        {transcript && transcript.length > 0 ? (
          transcript.map((item) => {
            const startPct = (item.timestampStart / total) * 100;
            const widthPct = Math.max(1, ((item.timestampEnd - item.timestampStart) / total) * 100);
            const color = item.speakerColor || speakerColorMap[item.speakerId] || '#6366f1';

            return (
              <div
                key={item.id}
                style={{
                  left: `${startPct}%`,
                  width: `${widthPct}%`,
                  backgroundColor: color,
                }}
                className="absolute top-0 bottom-0 opacity-80 hover:opacity-100 transition-opacity"
                title={`${item.speakerName} (${formatSecondsToTime(item.timestampStart)} - ${formatSecondsToTime(item.timestampEnd)})`}
              />
            );
          })
        ) : (
          <div className="w-full h-full bg-indigo-200/50" />
        )}

        {/* Current playback playhead line */}
        <div
          style={{ left: `${progressPercent}%` }}
          className="absolute top-0 bottom-0 w-1 bg-white shadow-md z-10 pointer-events-none transform -translate-x-1/2 flex items-center justify-center"
        >
          <div className="w-2.5 h-2.5 rounded-full bg-white shadow-md border border-slate-400" />
        </div>
      </div>

      {/* Speaker legend */}
      <div className="flex flex-wrap items-center gap-3 mt-2 text-[11px] text-slate-600">
        <span className="text-slate-400 font-medium">Speakers:</span>
        {speakers.map((spk) => (
          <button
            key={spk.id}
            onClick={() => {
              // Seek to first utterance of this speaker
              const firstUtt = transcript.find((t) => t.speakerId === spk.id || t.speakerName === spk.name);
              if (firstUtt) onSeek(firstUtt.timestampStart);
            }}
            className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
            title={`Jump to first utterance by ${spk.name}`}
          >
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0 shadow-2xs"
              style={{ backgroundColor: spk.color }}
            />
            <span className="font-medium text-slate-700">{spk.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
