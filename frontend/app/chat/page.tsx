// app/chat/page.tsx
"use client";

import { useState, useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { TopBar } from '@/components/layout/TopBar';
import { UserMessage } from '@/components/chat/UserMessage';
import { AgentMessage } from '@/components/chat/AgentMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { EmptyState } from '@/components/chat/EmptyState';
import { SettingsModal } from '@/components/settings/SettingsModal';
import { ToastContainer } from '@/components/ui/Toast';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAgent } from '@/hooks/useAgent';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';
import { api } from '@/lib/api';

type Toast = {
  id: number;
  type: 'success' | 'error' | 'info';
  title?: string;
  message?: string;
};

export default function ChatPage() {
  // Session management hooks
  const {
    sessions,
    currentSession,
    createSession,
    setCurrentSessionId,
    archiveSession,
  } = useSession(true);

  // Automatically select the latest session when sessions are loaded
  useEffect(() => {
    if (!currentSession && sessions.length > 0) {
      // Select the first session (most recent)
      const latestSession = sessions[0];
      setCurrentSessionId(latestSession.session_id);
    }
  }, [currentSession, sessions, setCurrentSessionId]);

  // Budget management hooks
  const {
    globalBudget,
    sessionBudget,
    loadGlobalBudget,
    loadSessionBudget,
    updateGlobalBudget,
    updateSessionBudget,
  } = useBudget(currentSession?.session_id);

  // Use the agent hook for chat functionality - pass currentSession to sync messages
  const { messages, isTyping, activeJobs, sendMessage, sessionId } = useAgent(
    currentSession?.session_id
  );

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Handle session creation
  const handleCreateSession = async (name: string, budget: number) => {
    try {
      const sessionId = await createSession({ session_name: name, budget_limit: budget });
      setCurrentSessionId(sessionId);
      addToast({
        type: 'success',
        title: 'Session Created',
        message: `${name} has been created`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Failed to Create Session',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  // Handle session selection - messages automatically load via useAgent hook
  const handleSelectSession = async (sessionId: string) => {
    try {
      setCurrentSessionId(sessionId);

      // Get session details for toast message
      const sessionDetail = await api.getSession(sessionId);

      addToast({
        type: 'info',
        title: 'Session Switched',
        message: `Switched to ${sessionDetail.session_name}`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Failed to Switch Session',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  // Handle session archiving
  const handleArchiveSession = async (sessionId: string) => {
    try {
      // Find the session name before archiving
      const session = sessions.find(s => s.session_id === sessionId);
      const sessionName = session?.session_name || 'Session';

      await archiveSession(sessionId);

      addToast({
        type: 'success',
        title: 'Session Archived',
        message: `${sessionName} has been archived`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Failed to Archive Session',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  // Handle budget updates
  const handleUpdateGlobalBudget = async (limit: number) => {
    await updateGlobalBudget(limit);
    await loadGlobalBudget();
  };

  const handleUpdateSessionBudget = async (sessionId: string, limit: number) => {
    await updateSessionBudget(sessionId, limit);
    await loadSessionBudget(sessionId);
  };

  // Handle sending messages - now uses the agent hook with SSE streaming
  const handleSendMessage = async (text: string) => {
    try {
      // The useAgent hook handles everything: user message, API call, SSE streaming, and job updates
      await sendMessage(text);

      // Show toast for any jobs that were started (activeJobs will be updated by the hook)
      // Check if new jobs were added after a short delay
      setTimeout(() => {
        if (activeJobs.length > 0) {
          const latestJob = activeJobs[activeJobs.length - 1];
          if (latestJob.status === 'running') {
            addToast({
              type: 'success',
              title: 'Training Job Started',
              message: `Job ${latestJob.id.slice(0, 8)} has been launched`,
            });
          }
        }
      }, 500);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Failed to send message';
      addToast({
        type: 'error',
        title: 'Connection Error',
        message: errorMsg,
      });
    }
  };

  const handleFileUpload = async (file?: File) => {
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch('/api/data/upload', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          addToast({
            type: 'success',
            title: 'Dataset Uploaded',
            message: `${file.name} has been versioned with DVC`,
          });
        }
      } catch (error: any) {
        addToast({
          type: 'error',
          title: 'Upload Failed',
          message: error?.message || String(error),
        });
      }
    };

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = Date.now();
    const t: Toast = { ...toast, id } as Toast;
    setToasts((prev) => [...prev, t]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((tt) => tt.id !== id));
    }, 5000);
  };

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ProtectedRoute>
      <div className="h-screen flex flex-col bg-gray-50">
        {/* Top Bar */}
        <TopBar
          user={{ name: 'John Doe', role: 'ML Engineer' }}
          budget={{
            spent: globalBudget?.spent || 0,
            limit: globalBudget?.limit || 500,
            remaining: globalBudget?.remaining || 500,
          }}
          onSettingsClick={() => setShowSettings(true)}
        />

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar */}
          <Sidebar
            activeJobs={activeJobs}
            budget={{
              spent: sessionBudget?.spent || 0,
              limit: sessionBudget?.limit || 50,
              remaining: sessionBudget?.remaining || 50,
            }}
            sessions={sessions}
            currentSessionId={currentSession?.session_id || null}
            onCreateSession={handleCreateSession}
            onSelectSession={handleSelectSession}
            onArchiveSession={handleArchiveSession}
          />

          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6">
              {messages.length === 0 ? (
                <EmptyState onQuickStart={handleSendMessage} />
              ) : (
                <>
                  {messages.map((msg, idx) => (
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
                        thinkingSteps={msg.data?.thinkingSteps}
                      />
                    )
                  ))}
                  <AnimatePresence>
                    {isTyping && <TypingIndicator />}
                  </AnimatePresence>
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input */}
            <ChatInput
              onSend={handleSendMessage}
              onFileUpload={handleFileUpload}
              isLoading={isTyping}
            />
          </div>
        </div>

        {/* Toast Notifications */}
        <ToastContainer toasts={toasts} onRemove={removeToast} />

        {/* Settings Modal */}
        <SettingsModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          globalBudget={globalBudget}
          sessionBudget={sessionBudget}
          sessions={sessions}
          onUpdateGlobalBudget={handleUpdateGlobalBudget}
          onUpdateSessionBudget={handleUpdateSessionBudget}
        />
      </div>
    </ProtectedRoute>
  );
}