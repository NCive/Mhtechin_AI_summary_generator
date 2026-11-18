import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  subtext?: string;
  fullHeight?: boolean;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading meeting intelligence...',
  subtext,
  fullHeight = false,
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center ${
        fullHeight ? 'min-h-[400px]' : 'py-12'
      }`}
    >
      <div className="relative mb-4">
        <div className="w-12 h-12 rounded-full border-4 border-indigo-100 animate-spin border-t-indigo-600" />
        <Loader2 className="w-6 h-6 text-indigo-600 absolute inset-0 m-auto animate-pulse" />
      </div>
      <p className="text-sm font-semibold text-slate-800">{message}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1 max-w-sm">{subtext}</p>}
    </div>
  );
};
