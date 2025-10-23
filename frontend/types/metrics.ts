export interface TrainingMetrics {
  job_id: string;
  epoch: number;
  total_epochs: number;
  
  loss: number;
  val_loss: number;
  accuracy: number;
  val_accuracy: number;
  
  gpu_utilization: number;
  memory_used_gb: number;
  memory_total_gb: number;
  
  learning_rate: number;
  batch_size: number;
  
  samples_processed: number;
  samples_per_second: number;
  
  timestamp: string;
}

export interface MetricsHistory {
  loss: number[];
  accuracy: number[];
  val_loss: number[];
  val_accuracy: number[];
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  gpu_percent: number;
  disk_usage_percent: number;
  network_io: {
    bytes_sent: number;
    bytes_recv: number;
  };
}