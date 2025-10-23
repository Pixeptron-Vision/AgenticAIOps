import { motion } from 'framer-motion';
import { Activity, Zap, CheckCircle2, AlertCircle } from 'lucide-react';
import { Progress } from '@/components/ui/Progress';
import { Job } from '@/types/jobs';

export function JobStatusCard({ data }: { data: Job }) {
  const { id, status, progress, metrics, eta, cost_so_far } = data;

  const statusConfig = {
    queued: {
      icon: Activity,
      color: 'text-gray-500',
      bgColor: 'bg-gray-50',
      borderColor: 'border-gray-200',
    },
    training: {
      icon: Activity,
      color: 'text-blue-500',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
    },
    completed: {
      icon: CheckCircle2,
      color: 'text-green-500',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
    },
    failed: {
      icon: AlertCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
    },
  };

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.training;
  const Icon = config.icon as any;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`mt-3 p-4 ${config.bgColor} border ${config.borderColor} rounded-xl`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${config.color}`} />
          <span className="text-sm font-semibold text-gray-800">
            Job: {id}
          </span>
        </div>
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          {status}
        </span>
      </div>

      {/* Progress Bar */}
      {status === 'training' && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-600">Progress</span>
            <span className="text-xs font-semibold text-gray-800">{progress}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      )}

      {/* Current Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 gap-2 mb-3">
          {Object.entries(metrics).map(([key, value]) => (
            <div key={key} className="bg-white/60 rounded-lg p-2">
              <p className="text-xs text-gray-500 capitalize">
                {key.replace('_', ' ')}
              </p>
              <p className="text-sm font-semibold text-gray-900">
                {typeof value === 'number' ? value.toFixed(3) : value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Footer Info */}
      <div className="flex items-center justify-between text-xs text-gray-600">
        <span className="flex items-center gap-1">
          <Zap className="w-3 h-3" />
          ETA: {eta} min
        </span>
        <span className="font-medium">${cost_so_far} spent</span>
      </div>
    </motion.div>
  );
}