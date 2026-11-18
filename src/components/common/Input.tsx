import React, { InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightElement?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  leftIcon,
  rightElement,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {leftIcon && (
          <div className="absolute left-3 flex items-center pointer-events-none text-slate-400">
            {leftIcon}
          </div>
        )}
        <input
          id={inputId}
          className={`w-full rounded-lg border text-sm text-slate-900 placeholder:text-slate-400 bg-white shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-slate-50 disabled:text-slate-500 ${
            leftIcon ? 'pl-9' : 'pl-3.5'
          } ${rightElement ? 'pr-20' : 'pr-3.5'} py-2.5 ${
            error ? 'border-rose-400 focus:ring-rose-500 focus:border-rose-500' : 'border-slate-300'
          } ${className}`}
          {...props}
        />
        {rightElement && (
          <div className="absolute right-2 flex items-center">
            {rightElement}
          </div>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
};
