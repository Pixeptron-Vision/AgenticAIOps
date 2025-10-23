'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Folder } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { SessionSummary } from '@/types/session';
import { SessionListItem } from './SessionListItem';

interface SessionsPanelProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onArchiveSession?: (sessionId: string) => void;
}

export function SessionsPanel({ sessions, currentSessionId, onSelectSession, onArchiveSession }: SessionsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="space-y-2">
      {/* Collapsible Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Folder className="w-5 h-5" />
          <span className="text-sm font-medium">Sessions</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
            {sessions.length}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </div>
      </button>

      {/* Expandable Session List */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pl-3 pr-1 space-y-2 max-h-96 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="text-center py-8 text-sm text-gray-500">
                  No sessions yet. Create one to get started!
                </div>
              ) : (
                sessions.map((session) => (
                  <SessionListItem
                    key={session.session_id}
                    session={session}
                    isActive={session.session_id === currentSessionId}
                    onClick={() => {
                      onSelectSession(session.session_id);
                      setIsExpanded(false);
                    }}
                    onArchive={onArchiveSession}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
