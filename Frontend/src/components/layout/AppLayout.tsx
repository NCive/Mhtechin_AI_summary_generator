import React from 'react';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-[#f3f4fa] text-[#141522] p-3 sm:p-5 lg:p-6 font-sans">
      <div className="w-full max-w-[1720px] mx-auto">
        {children}
      </div>
    </div>
  );
};
