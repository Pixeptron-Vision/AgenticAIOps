import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, ExternalLink, CheckCircle } from 'lucide-react';
import { Model } from '@/types/models';
import { formatBytes } from '@/lib/utils';

interface ModelDetailsProps {
  isOpen: boolean;
  onClose: () => void;
  model: Model | null;
}

export function ModelDetailsDialog({ isOpen, onClose, model }: ModelDetailsProps) {
  if (!model) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative w-full max-w-3xl bg-white rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="p-6 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-gray-200">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{model.name}</h2>
                  <p className="text-sm text-gray-600 mt-1">Version {model.version}</p>
                </div>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 max-h-[70vh] overflow-y-auto">
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <MetricBox label="Accuracy" value={`${(model.metrics.accuracy * 100).toFixed(1)}%`} />
                <MetricBox label="F1 Score" value={model.metrics.f1_score ? `${(model.metrics.f1_score * 100).toFixed(1)}%` : 'N/A'} />
                <MetricBox label="Latency (P95)" value={`${model.metrics.latency_p95_ms}ms`} />
                <MetricBox label="Model Size" value={formatBytes(model.metrics.model_size_mb * 1024 * 1024)} />
              </div>

              {/* Model Info */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Model Information</h3>
                <div className="grid grid-cols-2 gap-4">
                  <InfoRow label="Task Type" value={model.task_type} />
                  <InfoRow label="Base Model" value={model.base_model} />
                  <InfoRow label="Optimization" value={model.optimization} />
                  <InfoRow label="Stage" value={model.stage} />
                  <InfoRow label="Created By" value={model.metadata.created_by} />
                  <InfoRow label="Dataset Version" value={model.metadata.dataset_version} />
                  <InfoRow label="Training Duration" value={`${model.metadata.training_duration_minutes} min`} />
                  <InfoRow label="Training Cost" value={`$${model.metadata.cost.toFixed(2)}`} />
                </div>
              </div>

              {/* Deployment Info */}
              {model.deployment && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Deployment</h3>
                  <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
                    <div className="flex items-center gap-2 mb-3">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                      <span className="text-sm font-semibold text-green-900">Active Deployment</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Endpoint:</span>
                        <a
                          href={model.deployment.endpoint_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
                        >
                          View <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Requests/min:</span>
                        <span className="text-sm font-medium text-gray-900">{model.deployment.requests_per_minute}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Error Rate:</span>
                        <span className="text-sm font-medium text-gray-900">{(model.deployment.error_rate * 100).toFixed(2)}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Additional Metrics */}
              {model.metrics.precision && model.metrics.recall && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Detailed Metrics</h3>
                  <div className="grid grid-cols-3 gap-4">
                    <MetricBox label="Precision" value={`${(model.metrics.precision * 100).toFixed(1)}%`} />
                    <MetricBox label="Recall" value={`${(model.metrics.recall * 100).toFixed(1)}%`} />
                    <MetricBox label="Latency (P50)" value={`${model.metrics.latency_p50_ms}ms`} />
                  </div>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="p-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                Close
              </button>
              <button className="px-4 py-2 bg-white border border-gray-300 text-sm font-medium text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                <Download className="w-4 h-4" />
                Download
              </button>
              <button className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg">
                Deploy to Production
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 bg-gray-50 rounded-lg">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-lg font-bold text-gray-900">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-gray-500 mb-1">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}