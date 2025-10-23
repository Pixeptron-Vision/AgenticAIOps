// hooks/useAgent.ts
import { useState, useCallback, useEffect } from 'react';
import { Job } from '@/types/jobs';
import { getApiUrl } from '@/lib/config';

export type Message = {
  role: 'user' | 'agent';
  message?: string;
  timestamp: string;
  type?: string;
  data?: any;
};

export function useAgent(externalSessionId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);

  // Session ID: use external if provided, otherwise use localStorage
  const [sessionId, setSessionId] = useState(() => {
    if (externalSessionId) return externalSessionId;
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('currentSessionId');
      if (stored) return stored;
    }
    const newId = `session-${Date.now()}`;
    if (typeof window !== 'undefined') {
      localStorage.setItem('currentSessionId', newId);
    }
    return newId;
  });

  // Sync sessionId when externalSessionId changes
  useEffect(() => {
    if (externalSessionId && externalSessionId !== sessionId) {
      setSessionId(externalSessionId);
      // Clear messages immediately when switching sessions
      setMessages([]);
      if (typeof window !== 'undefined') {
        localStorage.setItem('currentSessionId', externalSessionId);
      }
    }
  }, [externalSessionId, sessionId]);

  const [showThinking, setShowThinking] = useState<boolean>(false);
  const [thinkingMessages, setThinkingMessages] = useState<Message[]>([]);

  // Guard to prevent double-calls
  const [isSending, setIsSending] = useState<boolean>(false);

  // Define helper functions first (before sendMessage uses them)
  const updateJob = useCallback((jobId: string, updates: Partial<Job>) => {
    setActiveJobs((prev) =>
      prev.map((job) => (job.id === jobId ? { ...job, ...updates } : job))
    );
  }, []);

  const addJob = useCallback((job: Job) => {
    setActiveJobs((prev) => [...prev, job]);
  }, []);

  const removeJob = useCallback((jobId: string) => {
    setActiveJobs((prev) => prev.filter((job) => job.id !== jobId));
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    // Guard: prevent double-calls
    if (isSending) {
      console.warn('⚠️ Blocked duplicate sendMessage call');
      return;
    }

    setIsSending(true);

    // Add user message
    const userMsg: Message = {
      role: 'user',
      message: text,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);

    try {
      // Use SSE streaming endpoint for real-time updates
      const response = await fetch(`${getApiUrl()}/api/agent/chat-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Parse SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let agentResponse = '';
      let currentThinkingSteps: string[] = []; // Track thinking steps for current response

      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;

            // Parse SSE event
            const eventMatch = line.match(/^event: (.+)/m);
            const dataMatch = line.match(/^data: (.+)/m);

            if (eventMatch && dataMatch) {
              const eventType = eventMatch[1];
              const eventData = JSON.parse(dataMatch[1]);

              // Handle different event types
              if (eventType === 'conversational_response') {
                // Add conversational response (from greetings, help, etc.)
                agentResponse += eventData.message;
              } else if (eventType === 'agent_thinking') {
                // Accumulate thinking steps for this response
                currentThinkingSteps.push(eventData.message);
              } else if (eventType === 'workflow_step') {
                // Accumulate workflow steps for this response
                currentThinkingSteps.push(`${eventData.step || 'Processing'}: ${eventData.message}`);
              } else if (eventType === 'candidates_found') {
                agentResponse += `\n\nFound ${eventData.count} model candidates:\n${eventData.models.join(', ')}`;
              } else if (eventType === 'jobs_launched') {
                eventData.job_ids.forEach((job_id: string, idx: number) => {
                  addJob({
                    id: job_id,
                    name: eventData.model ? `${eventData.model} Training` : job_id,
                    status: 'training',
                    progress: 0,
                    eta: 10, // Default estimate
                    cost_so_far: 0,
                    started_at: new Date().toISOString(),
                    type: 'training',
                    config: {
                      task_type: 'token-classification',
                      base_model: eventData.model || 'distilbert-base-cased',
                      dataset: 'DFKI-SLT/ciER',
                      optimization: 'LoRA',
                      constraints: {},
                    },
                  });
                });
                agentResponse += `\n\nLaunched ${eventData.count} training jobs`;
              } else if (eventType === 'recommendations_ready') {
                agentResponse += `\n\nTop recommendation: ${eventData.top_model}`;
              } else if (eventType === 'workflow_complete') {
                agentResponse += `\n\n✅ Workflow completed successfully!`;
              }
            }
          }
        }
      }

      // Add final agent response with thinking steps
      if (agentResponse) {
        setMessages((prev) => [...prev, {
          role: 'agent',
          message: agentResponse.trim(),
          type: 'text',
          timestamp: new Date().toLocaleTimeString(),
          data: {
            thinkingSteps: currentThinkingSteps.length > 0 ? currentThinkingSteps : undefined
          }
        }]);
      }

    } catch (error) {
      console.error('Failed to send message:', error);

      // Add error message to chat
      setMessages((prev) => [...prev, {
        role: 'agent',
        message: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
        type: 'error',
        timestamp: new Date().toLocaleTimeString(),
      }]);
    } finally {
      setIsTyping(false);
      setIsSending(false);  // Reset guard
    }
  }, [sessionId, addJob, isSending]);

  // Load session messages from database on mount
  useEffect(() => {
    const loadSessionMessages = async () => {
      if (!sessionId) return;

      try {
        const response = await fetch(`${getApiUrl()}/api/agent/chat/history/${sessionId}`);
        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages.map((msg: any) => ({
              role: msg.role === 'user' ? 'user' : 'agent',
              message: msg.content,
              timestamp: new Date(msg.timestamp).toLocaleTimeString(),
              type: msg.metadata?.type || 'text',
              data: {
                // Include thinking steps and workflow steps from metadata
                thinkingSteps: msg.metadata?.thinking_steps,
                workflowSteps: msg.metadata?.workflow_steps,
              }
            })));
          }
        }
      } catch (error) {
        console.error('Failed to load session messages:', error);
      }
    };

    loadSessionMessages();
  }, [sessionId]);

  // Load active jobs from database on mount
  useEffect(() => {
    const loadActiveJobs = async () => {
      try {
        // Load all jobs, then filter client-side for pending/training
        const response = await fetch(`${getApiUrl()}/api/jobs`);
        if (response.ok) {
          const data = await response.json();
          if (data.jobs && data.jobs.length > 0) {
            // Filter for active jobs (training or pending)
            const activeJobs = data.jobs.filter((job: any) =>
              job.status === 'training' || job.status === 'pending'
            );

            setActiveJobs(activeJobs.map((job: any) => ({
              id: job.job_id,
              name: `${job.config?.model_id || 'Model'} Training`,
              status: job.status,
              progress: job.progress || 0,
              eta: 10, // TODO: calculate from job data
              cost_so_far: job.cost_so_far || 0,
              started_at: job.created_at,
              type: 'training',
              config: {
                task_type: job.config?.task_type || 'token-classification',
                base_model: job.config?.model_id || 'distilbert-base-cased',
                dataset: job.config?.dataset || 'DFKI-SLT/ciER',
                optimization: job.config?.use_peft ? 'LoRA' : 'Full Fine-tune',
                constraints: {},
              },
            })));
          }
        }
      } catch (error) {
        console.error('Failed to load active jobs:', error);
      }
    };

    loadActiveJobs();

    // Poll for job updates every 10 seconds
    const interval = setInterval(loadActiveJobs, 10000);
    return () => clearInterval(interval);
  }, []);

  // Function to start a new chat session
  const startNewSession = useCallback(() => {
    const newId = `session-${Date.now()}`;
    setSessionId(newId);
    setMessages([]);
    if (typeof window !== 'undefined') {
      localStorage.setItem('currentSessionId', newId);
    }
  }, []);

  return {
    messages,
    isTyping,
    activeJobs,
    sendMessage,
    updateJob,
    addJob,
    removeJob,
    sessionId,
    showThinking,
    setShowThinking,
    thinkingMessages,
    startNewSession,
  };
}