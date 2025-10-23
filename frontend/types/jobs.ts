export interface Job {
  id: string;
  name: string;
  type: 'training' | 'deployment' | 'benchmark';
  status: 'queued' | 'training' | 'completed' | 'failed';
  progress: number;
  eta: number; // minutes
  cost_so_far: number;
  started_at: string;
  completed_at?: string;
  session_id?: string;

  config: {
    task_type: string;
    base_model: string;
    dataset: string;
    optimization: string;
    constraints: Record<string, any>;
  };

  metrics?: {
    accuracy?: number;
    loss?: number;
    f1_score?: number;
    latency_ms?: number;
    model_size_mb?: number;
    gpu_util?: number;
    memory_used?: number;
  };

  error?: string;
}

export interface JobUpdate {
  job_id: string;
  progress?: number;
  status?: Job['status'];
  metrics?: Job['metrics'];
  eta?: number;
}