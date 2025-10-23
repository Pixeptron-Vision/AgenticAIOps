'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Target, Download, ExternalLink, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Model } from '@/types/models';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';

export default function ModelsPage() {
  // Session management
  const { currentSession, sessions } = useSession(true);

  // Get session budget (not global budget)
  const { sessionBudget } = useBudget(currentSession?.session_id);

  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  // Budget display - fallback to defaults if not loaded
  const budget = sessionBudget || { spent: 0, limit: 50, remaining: 50 };

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      const data = await api.getModels();
      setModels(data);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <TopBar user={{ name: 'User', role: 'ML Engineer' }} budget={budget} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeJobs={[]}
          budget={budget}
          sessions={sessions}
          currentSessionId={currentSession?.session_id || null}
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Model Registry</h1>
            <p className="text-gray-600">Browse and manage your trained models</p>
          </div>

          {/* Models Grid */}
          {loading ? (
            <div>Loading...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {models.map((model) => (
                <ModelCard key={model.id} model={model} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelCard({ model }: { model: Model }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{model.name}</h3>
          <p className="text-sm text-gray-500">v{model.version}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
          model.stage === 'production' ? 'bg-green-100 text-green-700' :
          model.stage === 'staging' ? 'bg-blue-100 text-blue-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {model.stage}
        </span>
      </div>

      {/* Task Type */}
      <div className="mb-4 flex items-center gap-2">
        <Target className="w-4 h-4 text-gray-400" />
        <span className="text-sm text-gray-600">{model.task_type}</span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Accuracy</p>
          <p className="text-lg font-bold text-gray-900">{(model.metrics.accuracy * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Latency (P95)</p>
          <p className="text-lg font-bold text-gray-900">{model.metrics.latency_p95_ms}ms</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Model Size</p>
          <p className="text-lg font-bold text-gray-900">{model.metrics.model_size_mb}MB</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">F1 Score</p>
          <p className="text-lg font-bold text-gray-900">
            {model.metrics.f1_score ? (model.metrics.f1_score * 100).toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
      </div>

      {/* Deployment Status */}
      {model.deployment && (
        <div className="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-green-700">Deployed</span>
            <span className="text-xs text-green-600">{model.deployment.requests_per_minute} req/min</span>
          </div>

          <a
            href={model.deployment.endpoint_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-green-700 hover:text-green-800"
          >
            View endpoint <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button className="flex-1 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors text-sm font-medium">
          View Details
        </button>
        <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
          <Download className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}