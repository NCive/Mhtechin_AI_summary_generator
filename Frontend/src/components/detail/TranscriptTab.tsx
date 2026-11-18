import React, { useState } from 'react';
import { Search, Play, Filter } from 'lucide-react';
import { TranscriptUtterance, Speaker } from '../../types/meeting';
import { formatSecondsToTime } from '../../utils/formatters';

interface TranscriptTabProps {
  transcript: TranscriptUtterance[];
  speakers: Speaker[];
  currentTime?: number;
  onSeek: (seconds: number) => void;
}

export const TranscriptTab: React.FC<TranscriptTabProps> = ({
  transcript,
  speakers,
  currentTime = 0,
  onSeek,
}) => {
  const [filterText, setFilterText] = useState('');
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('all');

  const filteredTranscript = transcript.filter((item) => {
    const matchesText = item.text.toLowerCase().includes(filterText.toLowerCase()) ||
      item.speakerName.toLowerCase().includes(filterText.toLowerCase());
    const matchesSpeaker = selectedSpeaker === 'all' || item.speakerId === selectedSpeaker || item.speakerName === selectedSpeaker;
    return matchesText && matchesSpeaker;
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs space-y-4">
      {/* Transcript Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Search within spoken transcript..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {/* Filter by speaker */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={selectedSpeaker}
            onChange={(e) => setSelectedSpeaker(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none cursor-pointer"
          >
            <option value="all">All Speakers ({speakers.length})</option>
            {speakers.map((spk) => (
              <option key={spk.id} value={spk.id}>
                {spk.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Transcript Items */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
        {filteredTranscript.length > 0 ? (
          filteredTranscript.map((utterance) => {
            const isCurrent =
              currentTime >= utterance.timestampStart && currentTime <= utterance.timestampEnd;

            return (
              <div
                key={utterance.id}
                className={`p-3 rounded-lg border transition-all ${
                  isCurrent
                    ? 'bg-indigo-50/70 border-indigo-300 ring-1 ring-indigo-200'
                    : 'bg-white border-slate-200/80 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: utterance.speakerColor || '#4f46e5' }}
                    />
                    <span className="text-xs font-bold text-slate-900">{utterance.speakerName}</span>
                  </div>

                  <button
                    onClick={() => onSeek(utterance.timestampStart)}
                    className="flex items-center gap-1 text-[11px] font-mono text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded transition-colors group"
                    title="Jump to this point in recording"
                  >
                    <Play className="w-2.5 h-2.5 fill-current group-hover:scale-110 transition-transform" />
                    <span>{formatSecondsToTime(utterance.timestampStart)}</span>
                  </button>
                </div>

                <p className="text-xs text-slate-700 leading-relaxed pl-4 border-l-2 border-slate-200">
                  {utterance.text}
                </p>
              </div>
            );
          })
        ) : (
          <div className="text-center py-10 text-xs text-slate-400">
            No transcript matches for "{filterText}".
          </div>
        )}
      </div>
    </div>
  );
};
