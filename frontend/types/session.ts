/**
 * Session Management Types
 *
 * Types for managing chat sessions and their metadata.
 */

export interface SessionSummary {
  session_id: string;
  session_name: string;
  created_at: number;
  updated_at: number;
  last_message_at?: number;
  message_count: number;
  budget_spent: number;
  budget_limit: number;
  is_archived: boolean;
}

export interface SessionMessage {
  role: string;
  content: string;
  timestamp: string;
  metadata?: any;
}

export interface SessionDetail {
  session_id: string;
  session_name: string;
  created_at: number;
  updated_at: number;
  last_message_at?: number;
  budget_limit: number;
  is_archived: boolean;
  messages: SessionMessage[];
}

export interface CreateSessionRequest {
  session_name?: string;
  budget_limit?: number;
}

export interface CreateSessionResponse {
  session_id: string;
  session_name: string;
  budget_limit: number;
  created_at: string;
}

export interface UpdateSessionRequest {
  session_name?: string;
  budget_limit?: number;
}

export interface SessionsListResponse {
  sessions: SessionSummary[];
  total: number;
}
