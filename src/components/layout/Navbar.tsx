import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Sparkles, Video, History } from 'lucide-react';
import { ROUTES } from '../../constants/routes';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const isHome = location.pathname === ROUTES.HOME;

  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <Link to={ROUTES.HOME} className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
            <Sparkles className="w-5 h-5 text-indigo-100" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-lg text-slate-900 tracking-tight leading-none group-hover:text-indigo-600 transition-colors">
              Chatmeet
            </span>
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mt-0.5">
              AI Meeting Intelligence
            </span>
          </div>
        </Link>

        {/* Navigation & Status */}
        <nav className="flex items-center gap-2 sm:gap-4">
          <Link
            to={ROUTES.HOME}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              isHome
                ? 'bg-indigo-50 text-indigo-600'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <History className="w-4 h-4" />
            <span className="hidden sm:inline">Recent Meetings</span>
          </Link>

          <div className="h-4 w-px bg-slate-200 hidden sm:block" />

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              API Ready
            </span>
            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-semibold text-xs border border-white shadow-xs">
              <Video className="w-4 h-4 text-slate-500" />
            </div>
          </div>
        </nav>
      </div>
    </header>
  );
};
