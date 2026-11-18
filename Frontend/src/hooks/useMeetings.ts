import { useState, useEffect, useCallback } from 'react';
import { Meeting, JoinMeetingPayload, UploadMeetingPayload } from '../types/meeting';
import { getMeetings, joinMeeting, uploadMeeting } from '../services/meetingService';

export function useMeetings(initialQuery: string = '') {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchMeetings = useCallback(async (q?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getMeetings(q);
      setMeetings(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to load meetings.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMeetings(searchQuery);
  }, [fetchMeetings, searchQuery]);

  const handleJoin = async (payload: JoinMeetingPayload) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await joinMeeting(payload);
      await fetchMeetings(searchQuery);
      return result;
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to join online meeting.';
      setError(msg);
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpload = async (payload: UploadMeetingPayload) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await uploadMeeting(payload);
      await fetchMeetings(searchQuery);
      return result;
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to upload meeting recording.';
      setError(msg);
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    meetings,
    isLoading,
    error,
    searchQuery,
    setSearchQuery,
    refetch: () => fetchMeetings(searchQuery),
    joinMeetingAction: handleJoin,
    uploadMeetingAction: handleUpload,
    isSubmitting,
  };
}
