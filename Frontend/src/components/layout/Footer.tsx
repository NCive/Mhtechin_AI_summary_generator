import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-slate-200 bg-white py-6 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700">Chatmeet</span>
          <span>•</span>
          <span>AI Meeting Summary & Analytics Generator</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-slate-400">Strict 4-Endpoint API Integration</span>
          <span>•</span>
          <span className="text-slate-400">React + Vite + Tailwind CSS</span>
        </div>
      </div>
    </footer>
  );
};
