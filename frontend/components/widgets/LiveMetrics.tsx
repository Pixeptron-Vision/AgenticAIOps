// components/widgets/LiveMetrics.tsx
import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Zap, HardDrive } from 'lucide-react';
import { motion } from 'framer-motion';
import { JobUpdate } from '@/types/jobs';

interface LiveMetricsProps {
  jobId: string;
}

interface MetricsState {
  loss: { epoch: number; loss: number }[];
  accuracy: { epoch: number; acc: number }[];
  gpu_util: number;
  memory_used: number;
  memory_total: number;
}

export function LiveMetrics({ jobId }: LiveMetricsProps) {
  const [metrics, setMetrics] = useState<MetricsState>({
    loss: [],
    accuracy: [],
    gpu_util: 89,
    memory_used: 6.2,
    memory_total: 16,
  });

  useEffect(() => {
    // Connect to metrics stream
    const eventSource = new EventSource(`/api/metrics/${jobId}/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data) as JobUpdate;
      setMetrics((prev) => ({
        ...prev,
        loss: data.metrics?.loss ? [...prev.loss.slice(-20), { epoch: prev.loss.length, loss: data.metrics.loss }] : prev.loss,
        accuracy: data.metrics?.accuracy ? [...prev.accuracy.slice(-20), { epoch: prev.accuracy.length, acc: data.metrics.accuracy }] : prev.accuracy,
        gpu_util: data.metrics?.gpu_util || prev.gpu_util,
        memory_used: data.metrics?.memory_used || prev.memory_used,
      }));
    };

    return () => eventSource.close();
  }, [jobId]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl border border-gray-200 p-4"
    >
      <h3 className="text-sm font-bold text-gray-900 mb-4">Live Training Metrics</h3>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <MetricCard
          icon={Activity}
          label="GPU Util"
          value={`${metrics.gpu_util}%`}
          color="text-blue-600"
        />
        <MetricCard
          icon={Zap}
          label="Loss"
          value={metrics.loss[metrics.loss.length - 1]?.loss.toFixed(3) || '-'}
          color="text-purple-600"
        />
        <MetricCard
          icon={HardDrive}
          label="Memory"
          value={`${metrics.memory_used}/${metrics.memory_total}GB`}
          color="text-green-600"
        />
      </div>

      {/* Loss Chart */}
      <div className="mb-3">
        <p className="text-xs font-medium text-gray-600 mb-2">Training Loss</p>
        <ResponsiveContainer width="100%" height={100}>
          <LineChart data={metrics.loss}>
            <XAxis dataKey="epoch" hide />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(255,255,255,0.95)',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Line
              type="monotone"
              dataKey="loss"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              animationDuration={300}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Accuracy Chart */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-2">Validation Accuracy</p>
        <ResponsiveContainer width="100%" height={100}>
          <LineChart data={metrics.accuracy}>
            <XAxis dataKey="epoch" hide />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(255,255,255,0.95)',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Line
              type="monotone"
              dataKey="acc"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              animationDuration={300}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}

function MetricCard({ icon: Icon, label, value, color }: { icon: React.ElementType, label: string, value: string, color: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <Icon className={`w-4 h-4 ${color} mx-auto mb-1`} />
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-bold text-gray-900">{value}</p>
    </div>
  );
}