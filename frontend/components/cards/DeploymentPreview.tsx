// components/cards/DeploymentPreview.tsx
import { motion } from 'framer-motion';
import { ExternalLink, Copy, Download, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import { Model } from '@/types/models';

type Deployment = NonNullable<Model['deployment']>;

export function DeploymentPreview({ deployment }: { deployment: Deployment & { id: string } }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mt-3 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-4"
    >
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-bold text-blue-900">🚀 Deployment Ready</h4>
        <span className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded-full">
          <CheckCircle className="w-3 h-3" />
          Live
        </span>
      </div>

      {/* Endpoint URL */}
      <div className="mb-3">
        <label className="text-xs font-medium text-gray-600 mb-1 block">
          API Endpoint
        </label>
        <div className="flex items-center gap-2">
          <div className="flex-1 px-3 py-2 bg-white rounded-lg border border-gray-200 text-sm font-mono text-gray-800 truncate">
            {deployment.endpoint_url}
          </div>
          <button
            onClick={() => copyToClipboard(deployment.endpoint_url)}
            className="p-2 bg-white hover:bg-gray-50 border border-gray-200 rounded-lg transition-colors"
          >
            {copied ? (
              <CheckCircle className="w-4 h-4 text-green-600" />
            ) : (
              <Copy className="w-4 h-4 text-gray-600" />
            )}
          </button>

          <a
            href={deployment.endpoint_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 bg-white hover:bg-gray-50 border border-gray-200 rounded-lg transition-colors"
          >
            <ExternalLink className="w-4 h-4 text-gray-600" />
          </a>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-white/60 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-600">Requests/min</p>
          <p className="text-sm font-bold text-gray-900">{deployment.requests_per_minute}</p>
        </div>
        <div className="bg-white/60 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-600">Error Rate</p>
          <p className="text-sm font-bold text-green-600">{deployment.error_rate}%</p>
        </div>
        <div className="bg-white/60 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-600">Status</p>
          <p className="text-sm font-bold text-gray-900 capitalize">{deployment.status}</p>
        </div>
      </div>

      {/* Code Example */}
      <details className="group">
        <summary className="cursor-pointer list-none text-xs font-medium text-blue-700 hover:text-blue-800 mb-2">
          View code example →
        </summary>
        <div className="p-3 bg-gray-900 rounded-lg overflow-x-auto">
          <pre className="text-xs text-gray-100 font-mono">
{`curl -X POST ${deployment.endpoint_url} \\
  -H "Content-Type: application/json" \\
  -d '{"text": "This is a test"}'`}
          </pre>
        </div>
      </details>

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        <a
          href={`/dashboard/${deployment.id}`}
          className="flex-1 text-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          View Dashboard
        </a>
        <button className="px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg border border-gray-300 transition-colors">
          <Download className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}