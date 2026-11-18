import React, { useState } from 'react';
import { Search } from 'lucide-react';

interface MeetingMomentSearchProps {
  value: string;
  onChange: (query: string) => void;
  onSearch?: (query: string) => void;
  placeholder?: string;
}

export const MeetingMomentSearch: React.FC<MeetingMomentSearchProps> = ({
  value,
  onChange,
  onSearch,
  placeholder = 'Find any meeting moment...',
}) => {
  const [internalValue, setInternalValue] = useState(value);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onChange(internalValue);
    if (onSearch) onSearch(internalValue);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-2xl p-2 sm:p-2.5 flex items-center justify-between border border-[#ececf4] shadow-[0_2px_8px_rgba(0,0,0,0.02)]"
    >
      <div className="flex items-center gap-3 pl-3 flex-1 min-w-0">
        <Search className="w-4 h-4 text-gray-400 shrink-0" />
        <input
          type="text"
          value={internalValue}
          onChange={(e) => {
            setInternalValue(e.target.value);
            onChange(e.target.value);
          }}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm text-[#141522] placeholder:text-gray-400 focus:outline-none"
        />
      </div>
      <button
        type="submit"
        className="bg-[#5932ea] hover:bg-[#4b27d6] text-white text-sm font-medium px-6 py-2.5 rounded-xl transition-colors shrink-0 shadow-xs cursor-pointer"
      >
        Search
      </button>
    </form>
  );
};
