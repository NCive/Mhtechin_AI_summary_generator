import React, { useState, useEffect } from 'react';
import { useMeetings } from '../hooks/useMeetings';
import { useMeetingDetail } from '../hooks/useMeetingDetail';
import { MeetingMomentSearch } from '../components/meeting/MeetingMomentSearch';
import { NewMeetingSection } from '../components/meeting/NewMeetingSection';
import { RecentMeetingsList } from '../components/meeting/RecentMeetingsList';
import { MeetingDetailsView } from '../components/detail/MeetingDetailsView';
import { Toast } from '../components/common/Toast';
import { Meeting, JoinMeetingPayload, UploadMeetingPayload } from '../types/meeting';

export const HomePage: React.FC = () => {
  const {
    meetings,
    isLoading: isLoadingMeetings,
    error: meetingsError,
    searchQuery,
    setSearchQuery,
    refetch: refetchMeetings,
    joinMeetingAction,
    uploadMeetingAction,
    isSubmitting,
  } = useMeetings();

  const [selectedMeetingId, setSelectedMeetingId] = useState<string>('meet-weekly-sync');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  // Load selected meeting details
  const {
    meeting: activeMeeting,
    isLoading: isLoadingDetail,
    error: detailError,
    refetch: refetchDetail,
    toggleActionItem,
    toastMessage: detailToastMessage,
    toastType: detailToastType,
    clearToast: clearDetailToast,
  } = useMeetingDetail(selectedMeetingId);

  // Sync default selected meeting
  useEffect(() => {
    if (meetings.length > 0) {
      const exists = meetings.some((m) => m.id === selectedMeetingId);
      if (!exists && !selectedMeetingId) {
        setSelectedMeetingId(meetings[0].id);
      }
    }
  }, [meetings, selectedMeetingId]);

  const handleSelectMeeting = (meeting: Meeting) => {
    setSelectedMeetingId(meeting.id);
  };

  const handleJoinMeeting = async (payload: JoinMeetingPayload) => {
    try {
      const res = await joinMeetingAction(payload);
      setToastType('success');
      setToastMessage('Meeting joined successfully!');
      const newId = (res as { id?: string; meeting_id?: string }).id ||
        (res as { meeting_id?: string }).meeting_id;
      if (newId) {
        setSelectedMeetingId(newId);
      }
    } catch (err: unknown) {
      setToastType('error');
      setToastMessage((err as Error)?.message || 'Failed to join meeting.');
    }
  };

  const handleUploadMeeting = async (payload: UploadMeetingPayload) => {
    try {
      const res = await uploadMeetingAction(payload);
      setToastType('success');
      setToastMessage('Meeting recording uploaded successfully!');
      const newId = (res as { id?: string; meeting_id?: string }).id ||
        (res as { meeting_id?: string }).meeting_id;
      if (newId) {
        setSelectedMeetingId(newId);
      }
    } catch (err: unknown) {
      setToastType('error');
      setToastMessage((err as Error)?.message || 'Failed to upload meeting.');
    }
  };

  return (
    <div className="w-full">
      {/* 2-Column Exact Layout matching the reference image */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 lg:gap-6 items-start">
        {/* LEFT SECTION (Search, New Meeting, Online Meeting/Upload, Recent Meetings) */}
        <div className="xl:col-span-5 space-y-5">
          {/* 1. Meeting Moment Search */}
          <MeetingMomentSearch
            value={searchQuery}
            onChange={setSearchQuery}
            onSearch={setSearchQuery}
          />

          {/* 2. New Meeting (Online Meeting & Upload Meeting immediately beside) */}
          <NewMeetingSection
            onJoinMeeting={handleJoinMeeting}
            onUploadMeeting={handleUploadMeeting}
            isSubmitting={isSubmitting}
          />

          {/* 3. Recent Meetings */}
          <RecentMeetingsList
            meetings={meetings}
            selectedMeetingId={selectedMeetingId}
            onSelectMeeting={handleSelectMeeting}
            isLoading={isLoadingMeetings}
            error={meetingsError}
            onRetry={refetchMeetings}
          />
        </div>

        {/* RIGHT SECTION (Meeting Details, Summary, Key Points, Video Player, Speakers and Topics) */}
        <div className="xl:col-span-7">
          {isLoadingDetail ? (
            <div className="bg-white rounded-2xl p-12 text-center border border-[#ececf4]">
              <div className="w-8 h-8 border-3 border-[#5932ea] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-gray-700">Loading meeting details...</p>
            </div>
          ) : detailError || !activeMeeting ? (
            <div className="bg-white rounded-2xl p-8 text-center border border-rose-200">
              <p className="text-sm text-rose-600 mb-3">{detailError || 'Meeting details not found.'}</p>
              <button
                onClick={refetchDetail}
                className="text-xs font-semibold text-[#5932ea] underline"
              >
                Retry Loading
              </button>
            </div>
          ) : (
            <MeetingDetailsView
              meeting={activeMeeting}
              onBack={() => {
                if (meetings.length > 0) {
                  setSelectedMeetingId(meetings[0].id);
                }
              }}
              onToggleActionItem={toggleActionItem}
            />
          )}
        </div>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <Toast
          isOpen={!!toastMessage}
          message={toastMessage}
          onClose={() => setToastMessage(null)}
          type={toastType}
        />
      )}
      {detailToastMessage && (
        <Toast
          isOpen={!!detailToastMessage}
          message={detailToastMessage}
          onClose={clearDetailToast}
          type={detailToastType}
        />
      )}
    </div>
  );
};
