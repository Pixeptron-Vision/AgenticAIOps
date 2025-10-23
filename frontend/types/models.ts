export interface Model {
  id: string;
  name: string;
  version: string;
  task_type: string;
  base_model: string;
  optimization: string;
  
  metadata: {
    created_at: string;
    created_by: string;
    dataset_version: string;
    training_duration_minutes: number;
    cost: number;
  };
  
  metrics: {
    accuracy: number;
    f1_score?: number;
    precision?: number;
    recall?: number;
    latency_p50_ms: number;
    latency_p95_ms: number;
    model_size_mb: number;
  };
  
  deployment?: {
    endpoint_url: string;
    status: 'active' | 'inactive';
    requests_per_minute: number;
    error_rate: number;
  };
  
  stage: 'development' | 'staging' | 'production' | 'archived';
}

export interface ModelComparison {
  models: Model[];
  constraints: Record<string, number>;
}