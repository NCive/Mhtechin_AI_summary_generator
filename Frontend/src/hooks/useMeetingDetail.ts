import { useState, useEffect, useCallback } from 'react';
import { MeetingDetail, ActionItem } from '../types/meeting';
import { getMeetingById, updateActionItem } from '../services/meetingService';

export function useMeetingDetail(meetingId: string | undefined) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('error');

  const fetchMeeting = useCallback(async (isInitial: boolean = false) => {
    if (!meetingId) {
      setError(null);
      setMeeting(null);
      setIsLoading(false);
      return;
    }
    if (isInitial) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const data = await getMeetingById(meetingId);
      setMeeting(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to load meeting details.';
      setError(msg);
    } finally {
      if (isInitial) {
        setIsLoading(false);
      }
    }
  }, [meetingId]);

  useEffect(() => {
    fetchMeeting(true);
  }, [fetchMeeting]);

  // While status is 'scheduled' or 'processing', refresh meeting data every 5 seconds
  // Stop when it becomes 'completed' or 'failed' (and when leaving the page)
  useEffect(() => {
    if (!meetingId) return;
    if (meeting?.status !== 'scheduled' && meeting?.status !== 'processing') {
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const data = await getMeetingById(meetingId);
        setMeeting(data);
      } catch {
        // Silently catch polling errors to avoid transient error flashes
      }
    }, 5000);

    return () => clearInterval(intervalId);
  }, [meetingId, meeting?.status]);

  const toggleActionItem = useCallback(async (itemId: string) => {
    if (!meetingId) return;

    let previousDone = false;
    let nextDone = true;

    // 1. Tick immediately (optimistic UI update)
    setMeeting((prev) => {
      if (!prev || !prev.summary) return prev;
      const currentList =
        prev.summary.actionItems ||
        prev.summary.action_items ||
        prev.summary.key_points?.action_items ||
        [];

      const found = currentList.find(
        (it) => typeof it !== 'string' && it.id === itemId
      ) as ActionItem | undefined;

      previousDone = found ? Boolean(found.done ?? found.completed) : false;
      nextDone = !previousDone;

      const updateList = (list?: (string | ActionItem)[]) => {
        if (!list || !Array.isArray(list)) return list;
        return list.map((item) => {
          if (typeof item === 'string') return item;
          return item.id === itemId
            ? { ...item, done: nextDone, completed: nextDone }
            : item;
        });
      };

      const s = prev.summary;
      return {
        ...prev,
        summary: {
          ...s,
          ...(s.actionItems ? { actionItems: updateList(s.actionItems) } : {}),
          ...(s.action_items ? { action_items: updateList(s.action_items) } : {}),
          ...(s.key_points?.action_items
            ? {
                key_points: {
                  ...s.key_points,
                  action_items: updateList(s.key_points.action_items),
                },
              }
            : {}),
        },
      };
    });

    // 2. Send PATCH request
    try {
      await updateActionItem(meetingId, itemId, { done: nextDone });
    } catch (err: unknown) {
      // 3. Undo and show a toast if the request fails
      setMeeting((prev) => {
        if (!prev || !prev.summary) return prev;
        const revertList = (list?: (string | ActionItem)[]) => {
          if (!list || !Array.isArray(list)) return list;
          return list.map((item) => {
            if (typeof item === 'string') return item;
            return item.id === itemId
              ? { ...item, done: previousDone, completed: previousDone }
              : item;
          });
        };

        const s = prev.summary;
        return {
          ...prev,
          summary: {
            ...s,
            ...(s.actionItems ? { actionItems: revertList(s.actionItems) } : {}),
            ...(s.action_items ? { action_items: revertList(s.action_items) } : {}),
            ...(s.key_points?.action_items
              ? {
                  key_points: {
                    ...s.key_points,
                    action_items: revertList(s.key_points.action_items),
                  },
                }
              : {}),
          },
        };
      });

      const message = (err as Error)?.message || 'Failed to update action item.';
      setToastType('error');
      setToastMessage(message);
    }
  }, [meetingId]);

  return {
    meeting,
    isLoading,
    error,
    refetch: () => fetchMeeting(true),
    toggleActionItem,
    toastMessage,
    toastType,
    clearToast: () => setToastMessage(null),
  };
}
