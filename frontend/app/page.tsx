// app/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { TopBar } from '@/components/layout/TopBar';
import { UserMessage } from '@/components/chat/UserMessage';
import { AgentMessage } from '@/components/chat/AgentMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { EmptyState } from '@/components/chat/EmptyState';
import { KeyboardShortcuts } from '@/components/ui/KeyboardShortcuts';
import { SuccessCelebration } from '@/components/animations/SuccessCelebration';
import { ConstraintNegotiationDialog } from '@/components/dialogs/ConstraintNegotiation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAgent } from '@/hooks/useAgent';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';
import { useNotifications } from '@/contexts/NotificationContext';
import { api } from '@/lib/api';

export default function Home() {
  // Session management
  const { currentSession, sessions, setCurrentSessionId } = useSession(true);

  // Automatically select the latest session when sessions are loaded
  useEffect(() => {
    if (!currentSession && sessions.length > 0) {
      // Select the first session (most recent)
      const latestSession = sessions[0];
      setCurrentSessionId(latestSession.session_id);
    }
  }, [currentSession, sessions, setCurrentSessionId]);

  // Get session budget (not global budget)
  const { sessionBudget } = useBudget(currentSession?.session_id);

  const { messages, isTyping, activeJobs, sendMessage, updateJob, addJob } = useAgent(
    currentSession?.session_id
  );
  const { addNotification } = useNotifications();

  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);
  const [constraintDialog, setConstraintDialog] = useState<any | null>(null);

  const user = {
    name: 'Sarah Chen',
    role: 'ML Engineer',
  };

  // Budget display - fallback to defaults if not loaded
  const budget = sessionBudget || { spent: 0, limit: 50, remaining: 50 };

  // Debug logging
  useEffect(() => {
    console.log('🔍 Budget Debug:', {
      currentSessionId: currentSession?.session_id,
      sessionBudget,
      budgetUsed: budget,
    });
  }, [currentSession?.session_id, sessionBudget, budget]);

  // Poll for job updates every 10 seconds to keep sidebar in sync
  useEffect(() => {
    const pollJobs = async () => {
      try {
        const jobs = await api.getJobs();
        // Update activeJobs in useAgent hook
        const runningJobs = jobs.filter(j => j.status === 'training' || j.status === 'queued');
        runningJobs.forEach(job => {
          const existingJob = activeJobs.find(j => j.id === job.id);
          if (!existingJob) {
            // New job detected, add it
            addJob(job);
          } else if (existingJob.status !== job.status || existingJob.progress !== job.progress) {
            // Job status/progress changed, update it
            updateJob(job.id, job);
          }
        });
      } catch (error) {
        console.error('Failed to poll jobs:', error);
      }
    };

    // Initial poll
    pollJobs();

    // Poll every 10 seconds
    const intervalId = setInterval(pollJobs, 10000);

    return () => clearInterval(intervalId);
  }, [activeJobs, addJob, updateJob]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        if (e.key === '/') {
          e.preventDefault();
          setShowShortcuts(true);
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // SSE streaming handled in useAgent hook - notifications come through there
  // This is just a placeholder for future global SSE events
  useEffect(() => {
    // Global SSE events (job completions, alerts, etc.) can be added here
    // For now, all workflow events come through the chat-stream endpoint
  }, [addNotification]);

  const handleSendMessage = async (text: string) => {
    await sendMessage(text);
  };

  const handleFileUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/data/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        addNotification('success', 'Dataset Uploaded', `${file.name} has been versioned with DVC`);
      }
    } catch (error: any) {
      addNotification('error', 'Upload Failed', error?.message || String(error));
    }
  };

  return (
    <ProtectedRoute>
      <div className="h-screen flex flex-col bg-gradient-to-br from-gray-50 to-gray-100">
        {/* Top Bar */}
        <TopBar user={user} budget={budget} />

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
    {/* Sidebar */}
    <Sidebar
      activeJobs={activeJobs}
      budget={budget}
      sessions={sessions}
      currentSessionId={currentSession?.session_id || null}
    />

          {/* Chat Area */}
          <div className="flex-1 flex flex-col bg-white">
            {/* Messages Container */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 ? (
                <EmptyState onQuickStart={handleSendMessage} />
              ) : (
                <>
                  <AnimatePresence mode="popLayout">
                    {messages.map((msg, idx) =>
                      msg.role === 'user' ? (
                        <UserMessage
                          key={idx}
                          message={msg.message || ''}
                          timestamp={msg.timestamp}
                        />
                      ) : (
                        <AgentMessage
                          key={idx}
                          message={msg.message || ''}
                          type={msg.type}
                          data={msg.data}
                          timestamp={msg.timestamp}
                        />
                      )
                    )}
                  </AnimatePresence>

                  {isTyping && <TypingIndicator />}
                </>
              )}
            </div>

            {/* Input Area */}
            <ChatInput
              onSend={handleSendMessage}
              onFileUpload={handleFileUpload}
              isLoading={isTyping}
            />
          </div>
        </div>

        {/* Overlays */}
        <KeyboardShortcuts
          isOpen={showShortcuts}
          onClose={() => setShowShortcuts(false)}
        />

        {showCelebration && (
          <SuccessCelebration
            message="Your model is ready for production!"
            onComplete={() => setShowCelebration(false)}
          />
        )}

        {constraintDialog && (
          <ConstraintNegotiationDialog
            isOpen={!!constraintDialog}
            conflicts={constraintDialog.conflicts}
            alternatives={constraintDialog.alternatives}
            onClose={() => setConstraintDialog(null)}
            onSelect={(alternative: any) => {
              sendMessage(`Use ${alternative.name}`);
              setConstraintDialog(null);
            }}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}