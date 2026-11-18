import React, { useState, useRef } from 'react';
import {
  Mic,
  MicOff,
  Play,
  Pause,
  Users,
  Repeat,
  Square,
  MapPin,
  Sparkles,
} from 'lucide-react';
import { Speaker, TranscriptUtterance } from '../../types/meeting';

interface VideoPlayerProps {
  mediaUrl?: string;
  durationSeconds?: number;
  speakers?: Speaker[];
  transcript?: TranscriptUtterance[];
  seekTime?: number | null;
  onSeek?: (seconds: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  mediaUrl,
  durationSeconds = 1800,
  onSeek,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState('1x');
  const [isMuted, setIsMuted] = useState(false);
  const [showRealVideo, setShowRealVideo] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);

  const togglePlay = () => {
    if (mediaUrl) {
      if (!showRealVideo) setShowRealVideo(true);
      if (videoRef.current) {
        if (isPlaying) {
          videoRef.current.pause();
          setIsPlaying(false);
        } else {
          videoRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(true));
        }
      } else {
        setIsPlaying(!isPlaying);
      }
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const cycleSpeed = () => {
    const speeds = ['1x', '1.25x', '1.5x', '2x'];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    setPlaybackSpeed(speeds[nextIdx]);
    if (videoRef.current) {
      videoRef.current.playbackRate = parseFloat(speeds[nextIdx].replace('x', ''));
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)] overflow-hidden">
      {/* Video / Webcam Participant Tiles matching reference screenshot */}
      <div className="relative bg-slate-900 aspect-[16/10] overflow-hidden">
        {showRealVideo && mediaUrl ? (
          <video
            ref={videoRef}
            src={mediaUrl}
            onEnded={() => setIsPlaying(false)}
            onClick={togglePlay}
            className="w-full h-full object-contain cursor-pointer"
            playsInline
          />
        ) : (
          <div className="w-full h-full flex flex-col justify-between p-1.5 gap-1.5 bg-[#e8ebf5]">
            {/* Top row: 2 participant tiles */}
            <div className="grid grid-cols-2 gap-1.5 h-1/2">
              {/* Tile 1: Man in blue shirt */}
              <div className="relative rounded-xl overflow-hidden bg-slate-200">
                <img
                  src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=400&q=80"
                  alt="Brian Walker"
                  className="w-full h-full object-cover"
                />
                <span className="absolute bottom-1.5 left-2 bg-black/40 backdrop-blur-xs text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
                  Brian Walker
                </span>
              </div>

              {/* Tile 2: Woman in blue top */}
              <div className="relative rounded-xl overflow-hidden bg-slate-200">
                <img
                  src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80"
                  alt="Emily Wilson"
                  className="w-full h-full object-cover"
                />
                {/* Purple badge icon on top right as in reference image */}
                <div className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-[#5932ea] flex items-center justify-center text-white shadow-xs">
                  <Sparkles className="w-2.5 h-2.5 fill-current" />
                </div>
                <span className="absolute bottom-1.5 left-2 bg-black/40 backdrop-blur-xs text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
                  Emily Wilson
                </span>
              </div>
            </div>

            {/* Bottom row: 3 participant tiles */}
            <div className="grid grid-cols-3 gap-1.5 h-1/2">
              {/* Tile 3: Smiling woman */}
              <div className="relative rounded-xl overflow-hidden bg-slate-200">
                <img
                  src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=300&q=80"
                  alt="Participant"
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Tile 4: Man with glasses waving */}
              <div className="relative rounded-xl overflow-hidden bg-slate-200">
                <img
                  src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=300&q=80"
                  alt="Alex Brown"
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Tile 5: Man in blue shirt smiling */}
              <div className="relative rounded-xl overflow-hidden bg-slate-200">
                <img
                  src="https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=300&q=80"
                  alt="Noah Reynolds"
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Multi-colored Speaker Timeline Bar */}
      <div
        className="w-full h-1.5 flex cursor-pointer"
        onClick={() => onSeek && onSeek(durationSeconds * 0.3)}
        title="Speaker segments timeline"
      >
        <div className="h-full bg-[#4f7cf6] w-[22%]" />
        <div className="h-full bg-[#fcc419] w-[14%]" />
        <div className="h-full bg-[#20c997] w-[18%]" />
        <div className="h-full bg-[#3bc9db] w-[16%]" />
        <div className="h-full bg-[#845ef7] w-[20%]" />
        <div className="h-full bg-[#ff6b6b] w-[10%]" />
      </div>

      {/* Controls Bar */}
      <div className="p-3 flex items-center justify-center gap-3.5 bg-white">
        {/* Mic toggle */}
        <button
          type="button"
          onClick={() => setIsMuted(!isMuted)}
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
          aria-label="Microphone"
        >
          {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
        </button>

        {/* Speed */}
        <button
          type="button"
          onClick={cycleSpeed}
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-600 hover:text-gray-900 transition-colors cursor-pointer"
          title="Playback speed"
        >
          {playbackSpeed}
        </button>

        {/* Users */}
        <button
          type="button"
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
          aria-label="Participants"
        >
          <Users className="w-3.5 h-3.5" />
        </button>

        {/* Play / Pause button: solid purple circle */}
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

        {/* Sync/repeat */}
        <button
          type="button"
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
          aria-label="Repeat"
        >
          <Repeat className="w-3.5 h-3.5" />
        </button>

        {/* Square/Layout */}
        <button
          type="button"
          onClick={() => setShowRealVideo(!showRealVideo)}
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
          title="Toggle view"
        >
          <Square className="w-3.5 h-3.5" />
        </button>

        {/* Pin */}
        <button
          type="button"
          className="w-8 h-8 rounded-full bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
          aria-label="Pin"
        >
          <MapPin className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
