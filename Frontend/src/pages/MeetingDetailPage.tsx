import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMeetingDetail } from '../hooks/useMeetingDetail';
import { MeetingDetailsView } from '../components/detail/MeetingDetailsView';
import { Toast } from '../components/common/Toast';
import { ROUTES } from '../constants/routes';

export const MeetingDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    meeting,
    isLoading,
    error,
    refetch,
    toggleActionItem,
    toastMessage,
    toastType,
    clearToast,
  } = useMeetingDetail(id);

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl p-12 text-center border border-[#ececf4] max-w-4xl mx-auto my-8">
        <div className="w-8 h-8 border-3 border-[#5932ea] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm font-semibold text-gray-700">Loading meeting details...</p>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="bg-white rounded-2xl p-8 text-center border border-rose-200 max-w-lg mx-auto my-8">
        <p className="text-sm text-rose-600 mb-3">{error || 'Meeting not found.'}</p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={refetch}
            className="text-xs font-semibold text-[#5932ea] underline"
          >
            Retry
          </button>
          <button
            onClick={() => navigate(ROUTES.HOME)}
            className="text-xs font-semibold text-gray-600 hover:text-gray-900"
          >
            Return Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1280px] mx-auto py-2">
      <MeetingDetailsView
        meeting={meeting}
        onBack={() => navigate(ROUTES.HOME)}
        onToggleActionItem={toggleActionItem}
      />
      {toastMessage && (
        <Toast
          isOpen={!!toastMessage}
          message={toastMessage}
          onClose={clearToast}
          type={toastType}
        />
      )}
    </div>
  );
};
