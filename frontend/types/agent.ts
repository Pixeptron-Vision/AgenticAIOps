export interface Message {
  role: 'user' | 'agent';
  message: string;
  type?: 'text' | 'constraint_analysis' | 'recommendation' | 'job_status' | 'deployment';
  data?: any;
  timestamp: string;
}

import { Job } from './jobs';

export interface AgentState {
  sessionId: string;
  messages: Message[];
  isTyping: boolean;
  activeJobs: Job[];
}

export interface ConstraintAnalysis {
  dataset: {
    name: string;
    samples: number;
    classes: number;
  };
  compute: {
    available: number;
    used: number;
    total: number;
  };
  challenges?: string[];
}

export interface Recommendation {
  model: {
    name: string;
    params: string;
  };
  optimization: string;
  performance: {
    fps?: number;
    recall?: number;
    accuracy?: number;
  };
  cost: {
    amount: number;
    time: number;
  };
  alternatives?: Alternative[];
}

export interface Alternative {
  name: string;
  description: string;
  tradeoff: string;
  cost: number;
}

export interface Conflict {
  constraint: string;
  required: number | string;
  achievable: number | string;
  gap: number;
}