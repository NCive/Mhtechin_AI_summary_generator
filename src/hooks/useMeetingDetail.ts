import { useState, useEffect, useCallback } from 'react';
import { MeetingDetail } from '../types/meeting';
import { getMeetingById } from '../services/meetingService';

export function useMeetingDetail(meetingId: string | undefined) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeeting = useCallback(async () => {
    if (!meetingId) {
      setError('Meeting ID is missing.');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await getMeetingById(meetingId);
      setMeeting(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to load meeting details.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [meetingId]);

  useEffect(() => {
    fetchMeeting();
  }, [fetchMeeting]);

  const toggleActionItem = (itemId: string) => {
    if (!meeting || !meeting.summary) return;
    const currentActionItems = meeting.summary.actionItems || meeting.summary.action_items;
    if (!currentActionItems || !Array.isArray(currentActionItems)) return;

    setMeeting((prev) => {
      if (!prev || !prev.summary) return prev;
      const items = prev.summary.actionItems || prev.summary.action_items || [];
      const updatedActionItems = items.map((item) => {
        if (typeof item === 'string') return item;
        return item.id === itemId ? { ...item, completed: !item.completed } : item;
      });
      return {
        ...prev,
        summary: {
          ...prev.summary,
          actionItems: updatedActionItems,
        },
      };
    });
  };

  return {
    meeting,
    isLoading,
    error,
    refetch: fetchMeeting,
    toggleActionItem,
  };
}
