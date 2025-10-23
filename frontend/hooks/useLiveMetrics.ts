// hooks/useLiveMetrics.ts
import { useState, useEffect } from 'react';
import { TrainingMetrics } from '@/types/metrics';

interface MetricsWithHistory extends TrainingMetrics {
  history?: {
    loss: number[];
    accuracy: number[];
  };
}

export function useLiveMetrics(jobId: string | null) {
  const [metrics, setMetrics] = useState<MetricsWithHistory | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    const eventSource = new EventSource(`/api/metrics/${jobId}/stream`);

    eventSource.onopen = () => {
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data) as TrainingMetrics;
      setMetrics((prev) => ({
        ...data,
        history: {
          loss: [...(prev?.history?.loss || []).slice(-50), data.loss],
          accuracy: [...(prev?.history?.accuracy || []).slice(-50), data.accuracy],
        },
      }));
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [jobId]);

  return { metrics, isConnected };
}