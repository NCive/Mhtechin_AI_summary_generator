import React, { useState, useRef, useEffect } from 'react';
import {
  Mic,
  MicOff,
  Play,
  Pause,
  Square,
  Volume2,
} from 'lucide-react';
import { Speaker, TranscriptUtterance } from '../../types/meeting';
import { formatSecondsToTime } from '../../utils/formatters';
import { resolveMediaUrl } from '../../utils/mediaUtils';

interface VideoPlayerProps {
  mediaUrl?: string;
  mediaType?: 'audio' | 'video' | null;
  durationSeconds?: number | null;
  speakers?: Speaker[];
  transcript?: TranscriptUtterance[];
  seekTime?: number | null;
  seekTarget?: { time: number; id: number } | null;
  onSeek?: (seconds: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  mediaUrl,
  mediaType,
  speakers = [],
  transcript = [],
  seekTime,
  seekTarget,
  onSeek,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [mediaDuration, setMediaDuration] = useState<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = useState('1x');
  const [isMuted, setIsMuted] = useState(false);
  const [showRealVideo, setShowRealVideo] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const resolvedUrl = resolveMediaUrl(mediaUrl);

  const safeSpeakers = speakers || [];
  const safeTranscript = transcript || [];

  // Duration must use the media element's own duration (from loadedmetadata), not durationSeconds from the API
  const transcriptMax = safeTranscript.length > 0
    ? Math.max(...safeTranscript.map((t) => t.timestampEnd ?? t.timestampStart ?? 0))
    : 0;
  const totalDuration = mediaDuration > 0 ? mediaDuration : transcriptMax;

  // Reset playback and duration when media source changes
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setMediaDuration(0);
  }, [resolvedUrl]);

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLMediaElement>) => {
    const d = e.currentTarget.duration;
    if (typeof d === 'number' && !isNaN(d) && isFinite(d) && d > 0) {
      setMediaDuration(d);
    }
  };

  // Active utterance at current playback time
  const activeSegment = safeTranscript.find(
    (seg) =>
      currentTime >= (seg.timestampStart ?? 0) &&
      currentTime <= (seg.timestampEnd ?? seg.timestampStart ?? 0)
  );

  const isSpeakerActive = (spk: Speaker): boolean => {
    if (!activeSegment) return false;
    if (activeSegment.speakerId && spk.id === activeSegment.speakerId) return true;
    const segName = (activeSegment.speakerName ?? '').trim().toLowerCase();
    const spkName = (spk.name ?? '').trim().toLowerCase();
    if (segName && spkName && segName === spkName) {
      return true;
    }
    return false;
  };

  const getActiveMediaElement = () => {
    if (mediaType === 'audio') {
      return audioRef.current;
    }
    return videoRef.current;
  };

  // Synchronize seek requests from props (transcript click)
  useEffect(() => {
    const target = seekTarget ? seekTarget.time : seekTime;
    if (target != null) {
      const mediaEl = getActiveMediaElement();
      if (mediaEl) {
        mediaEl.currentTime = target;
      }
      setCurrentTime(target);
    }
  }, [seekTime, seekTarget]);

  const togglePlay = () => {
    if (resolvedUrl) {
      if (!showRealVideo) setShowRealVideo(true);
      const mediaEl = getActiveMediaElement();
      if (mediaEl) {
        if (isPlaying) {
          mediaEl.pause();
          setIsPlaying(false);
        } else {
          mediaEl
            .play()
            .then(() => setIsPlaying(true))
            .catch(() => setIsPlaying(true));
        }
      } else {
        setIsPlaying(!isPlaying);
      }
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const toggleMute = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    const mediaEl = getActiveMediaElement();
    if (mediaEl) {
      mediaEl.muted = nextMuted;
    }
  };

  const cycleSpeed = () => {
    const speeds = ['1x', '1.25x', '1.5x', '2x'];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    const speedStr = speeds[nextIdx];
    setPlaybackSpeed(speedStr);
    const mediaEl = getActiveMediaElement();
    if (mediaEl) {
      mediaEl.playbackRate = parseFloat(speedStr.replace('x', ''));
    }
  };

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (totalDuration <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    const targetTime = ratio * totalDuration;

    const mediaEl = getActiveMediaElement();
    if (mediaEl) {
      mediaEl.currentTime = targetTime;
    }
    setCurrentTime(targetTime);
    if (onSeek) {
      onSeek(targetTime);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] overflow-hidden">
      {/* Hidden audio element for audio playback */}
      {mediaType === 'audio' && resolvedUrl && (
        <audio
          key={`audio-${resolvedUrl}`}
          ref={audioRef}
          src={resolvedUrl}
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={() => {
            if (audioRef.current) {
              setCurrentTime(audioRef.current.currentTime);
              if (!mediaDuration && audioRef.current.duration && isFinite(audioRef.current.duration) && audioRef.current.duration > 0) {
                setMediaDuration(audioRef.current.duration);
              }
            }
          }}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          className="hidden"
        />
      )}

      {/* Main Player Display Area (Audio Player / Video / Speaker Tiles) */}
      <div className="relative bg-slate-900 aspect-[16/10] overflow-hidden">
        {(showRealVideo || safeSpeakers.length === 0) && resolvedUrl ? (
          mediaType === 'audio' ? (
            /* Simple Audio Player matching style */
            <div className="w-full h-full flex flex-col items-center justify-center p-6 bg-slate-900 text-white select-none">
              <div className="w-14 h-14 rounded-2xl bg-indigo-600/30 border border-indigo-400/30 flex items-center justify-center mb-3 shadow-lg">
                <Volume2 className="w-7 h-7 text-indigo-300 animate-pulse" />
              </div>
              <p className="text-xs font-semibold text-slate-300 mb-3 tracking-wide">
                Audio Recording
              </p>

              {/* Seek bar */}
              <div
                className="w-full max-w-xs h-2 bg-slate-700 rounded-full cursor-pointer relative overflow-hidden mb-2"
                onClick={handleTimelineClick}
                title="Seek audio"
              >
                <div
                  className="h-full bg-[#5932ea] rounded-full transition-all"
                  style={{
                    width: `${totalDuration > 0 ? Math.min(100, (currentTime / totalDuration) * 100) : 0}%`,
                  }}
                />
              </div>

              {/* Time display */}
              <span className="text-[11px] font-mono text-slate-400 mb-4">
                {formatSecondsToTime(currentTime)} / {formatSecondsToTime(totalDuration)}
              </span>

              {/* Play / pause button */}
              <button
                type="button"
                onClick={togglePlay}
                className="w-10 h-10 rounded-full bg-[#5932ea] hover:bg-[#4b27d6] flex items-center justify-center text-white shadow-md shadow-purple-500/20 transition-all hover:scale-105 cursor-pointer"
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isPlaying ? (
                  <Pause className="w-4 h-4 fill-current" />
                ) : (
                  <Play className="w-4 h-4 fill-current ml-0.5" />
                )}
              </button>
            </div>
          ) : (
            <video
              key={`video-${resolvedUrl}`}
              ref={videoRef}
              src={resolvedUrl}
              onLoadedMetadata={handleLoadedMetadata}
              onTimeUpdate={() => {
                if (videoRef.current) {
                  setCurrentTime(videoRef.current.currentTime);
                  if (!mediaDuration && videoRef.current.duration && isFinite(videoRef.current.duration) && videoRef.current.duration > 0) {
                    setMediaDuration(videoRef.current.duration);
                  }
                }
              }}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onClick={togglePlay}
              className="w-full h-full object-contain cursor-pointer"
              playsInline
            />
          )
        ) : safeSpeakers.length > 0 ? (
          <div className="w-full h-full p-2.5 bg-[#e8ebf5] overflow-auto">
            <div
              className={`grid gap-2 h-full ${
                safeSpeakers.length === 1
                  ? 'grid-cols-1'
                  : safeSpeakers.length === 2
                  ? 'grid-cols-2'
                  : safeSpeakers.length <= 4
                  ? 'grid-cols-2'
                  : 'grid-cols-3'
              }`}
            >
              {safeSpeakers.map((spk) => {
                const isActive = isSpeakerActive(spk);
                return (
                  <div
                    key={spk.id}
                    className={`relative rounded-xl p-3 flex flex-col items-center justify-center transition-all ${
                      isActive
                        ? 'bg-white border-2 border-[#5932ea] shadow-[0_4px_14px_rgba(89,50,234,0.18)] scale-[1.02]'
                        : 'bg-white/80 border border-slate-200/80 hover:bg-white'
                    }`}
                  >
                    {/* Initials in colored circle using speaker's color */}
                    <div
                      className={`w-11 h-11 sm:w-12 sm:h-12 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-xs transition-transform ${
                        isActive ? 'scale-105 ring-3 ring-[#5932ea]/30' : ''
                      }`}
                      style={{ backgroundColor: spk.color || '#94a3b8' }}
                    >
                      {(spk.name ?? '').trim() ? (spk.name ?? '').trim().charAt(0).toUpperCase() : '?'}
                    </div>

                    {/* Speaker Name */}
                    <span
                      className={`mt-2 text-xs font-bold truncate max-w-[95%] text-center ${
                        isActive ? 'text-[#5932ea]' : 'text-[#141522]'
                      }`}
                    >
                      {spk.name || 'Unknown speaker'}
                    </span>

                    {/* Role if present */}
                    {spk.role && (
                      <span className="text-[10px] text-gray-400 truncate max-w-[95%]">
                        {spk.role}
                      </span>
                    )}

                    {/* Active speaking indicator badge */}
                    {isActive && (
                      <span className="absolute top-2 right-2 flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {/* Speaker timeline bar built from real transcript segments */}
      {safeTranscript.length > 0 && totalDuration > 0 ? (
        <div
          className="w-full h-2 flex cursor-pointer bg-slate-100 relative overflow-hidden"
          onClick={handleTimelineClick}
          title="Click to seek"
        >
          {safeTranscript.map((seg, idx) => {
            const start = seg.timestampStart ?? 0;
            const end = seg.timestampEnd ?? start;
            const segDuration = Math.max(0, end - start);
            const widthPercent = (segDuration / totalDuration) * 100;
            const segSpeakerName = (seg.speakerName ?? '').trim().toLowerCase();
            const spk = safeSpeakers.find(
              (s) =>
                (seg.speakerId && s.id === seg.speakerId) ||
                (segSpeakerName && (s.name ?? '').trim().toLowerCase() === segSpeakerName)
            );
            const color = spk?.color || seg.speakerColor || '#94a3b8';

            return (
              <div
                key={seg.id || idx}
                style={{
                  width: `${widthPercent}%`,
                  backgroundColor: color,
                }}
                className="h-full hover:opacity-80 transition-opacity"
                title={`${seg.speakerName || 'Unknown speaker'} (${formatSecondsToTime(start)} - ${formatSecondsToTime(end)})`}
              />
            );
          })}

          {/* Current playback position indicator */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-black/80 shadow-xs pointer-events-none"
            style={{ left: `${Math.min(100, (currentTime / totalDuration) * 100)}%` }}
          />
        </div>
      ) : null}

      {/* Controls Bar */}
      <div className="p-3 flex items-center justify-between px-4 bg-white border-t border-gray-50">
        <span className="text-[11px] font-mono text-gray-500">
          {formatSecondsToTime(currentTime)} / {formatSecondsToTime(totalDuration)}
        </span>

        <div className="flex items-center gap-3">
          {/* Mic mute toggle */}
          <button
            type="button"
            onClick={toggleMute}
            className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
            aria-label={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
          </button>

          {/* Playback speed */}
          <button
            type="button"
            onClick={cycleSpeed}
            className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-600 hover:text-gray-900 transition-colors cursor-pointer"
            title="Playback speed"
          >
            {playbackSpeed}
          </button>

          {/* Play / Pause button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-10 h-10 rounded-full bg-[#5932ea] hover:bg-[#4b27d6] flex items-center justify-center text-white shadow-md shadow-purple-500/20 transition-all hover:scale-105 cursor-pointer"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 fill-current" />
            ) : (
              <Play className="w-4 h-4 fill-current ml-0.5" />
            )}
          </button>

          {/* Toggle View (Media vs speaker tiles) */}
          {resolvedUrl && (
            <button
              type="button"
              onClick={() => setShowRealVideo(!showRealVideo)}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-gray-500 transition-colors cursor-pointer ${
                showRealVideo ? 'bg-indigo-50 text-[#5932ea]' : 'bg-gray-50 hover:bg-gray-100'
              }`}
              title="Toggle media / speaker view"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="w-16" />
      </div>
    </div>
  );
};
