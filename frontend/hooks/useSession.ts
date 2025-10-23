import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import {
  SessionSummary,
  SessionDetail,
  CreateSessionRequest,
  UpdateSessionRequest
} from '@/types/session';

interface UseSessionReturn {
  // State
  sessions: SessionSummary[];
  currentSession: SessionDetail | null;
  loading: boolean;
  error: string | null;

  // Actions
  loadSessions: (includeArchived?: boolean) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  createSession: (request: CreateSessionRequest) => Promise<string>;
  updateSession: (sessionId: string, request: UpdateSessionRequest) => Promise<void>;
  archiveSession: (sessionId: string) => Promise<void>;
  setCurrentSessionId: (sessionId: string | null) => void;
}

export function useSession(autoLoad: boolean = true): UseSessionReturn {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentSession, setCurrentSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all sessions
  const loadSessions = useCallback(async (includeArchived: boolean = false) => {
    try {
      setLoading(true);
      setError(null);
      const sessionsList = await api.getSessions(includeArchived);
      setSessions(sessionsList);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load sessions';
      setError(errorMessage);
      console.error('Error loading sessions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load specific session details
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      setLoading(true);
      setError(null);
      const session = await api.getSession(sessionId);
      setCurrentSession(session);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load session';
      setError(errorMessage);
      console.error('Error loading session:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Create new session
  const createSession = useCallback(async (request: CreateSessionRequest): Promise<string> => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.createSession(request);

      // Reload sessions list
      await loadSessions();

      return response.session_id;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create session';
      setError(errorMessage);
      console.error('Error creating session:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadSessions]);

  // Update session
  const updateSession = useCallback(async (sessionId: string, request: UpdateSessionRequest) => {
    try {
      setLoading(true);
      setError(null);
      await api.updateSession(sessionId, request);

      // Reload sessions list and current session if it's the one being updated
      await loadSessions();
      if (currentSession?.session_id === sessionId) {
        await loadSession(sessionId);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update session';
      setError(errorMessage);
      console.error('Error updating session:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [currentSession, loadSessions, loadSession]);

  // Archive session
  const archiveSession = useCallback(async (sessionId: string) => {
    try {
      setLoading(true);
      setError(null);
      await api.archiveSession(sessionId);

      // Reload sessions list
      await loadSessions();

      // Clear current session if it was archived
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to archive session';
      setError(errorMessage);
      console.error('Error archiving session:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [currentSession, loadSessions]);

  // Set current session (loads it if not already loaded)
  const setCurrentSessionId = useCallback((sessionId: string | null) => {
    if (sessionId) {
      loadSession(sessionId);
    } else {
      setCurrentSession(null);
    }
  }, [loadSession]);

  // Auto-load sessions on mount if requested
  useEffect(() => {
    if (autoLoad) {
      loadSessions();
    }
  }, [autoLoad, loadSessions]);

  return {
    sessions,
    currentSession,
    loading,
    error,
    loadSessions,
    loadSession,
    createSession,
    updateSession,
    archiveSession,
    setCurrentSessionId,
  };
}
