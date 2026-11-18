import React, { useEffect } from 'react';
import { CheckCircle2, AlertTriangle, X, Info } from 'lucide-react';

export interface ToastProps {
  type?: 'success' | 'warning' | 'error' | 'info';
  message: string;
  isOpen: boolean;
  onClose: () => void;
  duration?: number;
}

export const Toast: React.FC<ToastProps> = ({
  type = 'success',
  message,
  isOpen,
  onClose,
  duration = 3000,
}) => {
  useEffect(() => {
    if (isOpen && duration > 0) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [isOpen, duration, onClose]);

  if (!isOpen) return null;

  const typeConfig = {
    success: {
      bg: 'bg-emerald-900/90 text-white border-emerald-700',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-300 shrink-0" />,
    },
    error: {
      bg: 'bg-rose-900/90 text-white border-rose-700',
      icon: <AlertTriangle className="w-5 h-5 text-rose-300 shrink-0" />,
    },
    warning: {
      bg: 'bg-amber-900/90 text-white border-amber-700',
      icon: <AlertTriangle className="w-5 h-5 text-amber-300 shrink-0" />,
    },
    info: {
      bg: 'bg-slate-900/90 text-white border-slate-700',
      icon: <Info className="w-5 h-5 text-slate-300 shrink-0" />,
    },
  };

  const current = typeConfig[type];

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-5 duration-200">
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-xl max-w-sm ${current.bg}`}
      >
        {current.icon}
        <p className="text-sm font-medium leading-snug">{message}</p>
        <button
          onClick={onClose}
          className="ml-auto p-1 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
