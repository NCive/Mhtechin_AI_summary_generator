export const MEETING_TABS = {
  SUMMARY: 'summary',
  TRANSCRIPT: 'transcript',
} as const;

export const SIDE_TABS = {
  SPEAKERS: 'speakers',
} as const;

export const MEETING_STATUS_STYLES = {
  completed: {
    bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot: 'bg-emerald-500',
    label: 'Completed',
  },
  processing: {
    bg: 'bg-amber-50 text-amber-700 border-amber-200',
    dot: 'bg-amber-500 animate-pulse',
    label: 'Processing',
  },
  scheduled: {
    bg: 'bg-blue-50 text-blue-700 border-blue-200',
    dot: 'bg-blue-500',
    label: 'Scheduled',
  },
  failed: {
    bg: 'bg-rose-50 text-rose-700 border-rose-200',
    dot: 'bg-rose-500',
    label: 'Failed',
  },
} as const;

export const SPEAKER_COLORS = [
  '#4f46e5', // indigo
  '#0891b2', // cyan
  '#059669', // emerald
  '#d97706', // amber
  '#dc2626', // red
  '#7c3aed', // violet
  '#db2777', // pink
];
