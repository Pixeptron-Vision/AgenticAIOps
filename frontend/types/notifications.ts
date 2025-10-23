export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  jobId?: string;
  metadata?: {
    oldStatus?: string;
    newStatus?: string;
    cost?: number;
    metrics?: any;
  };
}

export type NotificationType = Notification['type'];
