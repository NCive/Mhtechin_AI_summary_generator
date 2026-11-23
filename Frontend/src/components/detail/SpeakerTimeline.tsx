import React, { useMemo } from 'react';
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
  const speakerColorMap = (speakers || []).reduce((acc, spk) => {
    const color = spk.color || '#94a3b8';
    if (spk.id) acc[spk.id] = color;
    if (spk.name) acc[spk.name] = color;
    return acc;
  }, {} as Record<string, string>);

  // Deduplicate and filter out empty names for the speaker list
  const validSpeakers = useMemo(() => {
    const seen = new Set<string>();
    const list: Speaker[] = [];
    for (const spk of (speakers || [])) {
      const name = (spk.name ?? '').trim();
      if (!name) continue;
      const key = name.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        list.push({ ...spk, name });
      }
    }
    return list;
  }, [speakers]);

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
            const start = item.timestampStart ?? 0;
            const end = item.timestampEnd ?? start;
            const startPct = (start / total) * 100;
            const widthPct = Math.max(1, ((end - start) / total) * 100);
            const color =
              item.speakerColor ||
              (item.speakerId ? speakerColorMap[item.speakerId] : undefined) ||
              (item.speakerName ? speakerColorMap[item.speakerName] : undefined) ||
              '#94a3b8';

            return (
              <div
                key={item.id}
                style={{
                  left: `${startPct}%`,
                  width: `${widthPct}%`,
                  backgroundColor: color,
                }}
                className="absolute top-0 bottom-0 opacity-80 hover:opacity-100 transition-opacity"
                title={`${item.speakerName || 'Unknown speaker'} (${formatSecondsToTime(start)} - ${formatSecondsToTime(end)})`}
              />
            );
          })
        ) : (
          <div className="w-full h-full bg-slate-200" />
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
        {validSpeakers.map((spk) => (
          <button
            key={spk.id || spk.name}
            onClick={() => {
              // Seek to first utterance of this speaker
              const spkNameLower = (spk.name ?? '').trim().toLowerCase();
              const firstUtt = (transcript || []).find(
                (t) =>
                  (t.speakerId && t.speakerId === spk.id) ||
                  (spkNameLower && (t.speakerName ?? '').trim().toLowerCase() === spkNameLower)
              );
              if (firstUtt) onSeek(firstUtt.timestampStart ?? 0);
            }}
            className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
            title={`Jump to first utterance by ${spk.name || 'Unknown speaker'}`}
          >
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0 shadow-2xs"
              style={{ backgroundColor: spk.color || '#94a3b8' }}
            />
            <span className="font-medium text-slate-700">{spk.name || 'Unknown speaker'}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
