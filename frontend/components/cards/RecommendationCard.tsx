import { motion } from 'framer-motion';
import { TrendingUp, DollarSign, Clock, Cpu } from 'lucide-react';
import { Recommendation, Alternative } from '@/types/agent';

export function RecommendationCard({ data }: { data: Recommendation }) {
  const { model, optimization, performance, cost, alternatives } = data;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mt-3 overflow-hidden"
    >
      {/* Primary Recommendation */}
      <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4 mb-3">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-bold text-green-900">
            ⭐ Recommended Strategy
          </h4>
          <span className="px-2 py-1 bg-green-200 text-green-800 text-xs font-semibold rounded-full">
            Best Match
          </span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-700">Model</span>
            <span className="text-sm font-semibold text-gray-900">{model.name}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-700">Optimization</span>
            <span className="text-sm font-mono text-gray-900">{optimization}</span>
          </div>
        </div>

        {/* Performance Metrics Grid */}
        <div className="grid grid-cols-3 gap-3 mt-4">
          <div className="bg-white/60 rounded-lg p-2 text-center">
            <TrendingUp className="w-4 h-4 text-green-600 mx-auto mb-1" />
            <p className="text-xs text-gray-600">Performance</p>
            <p className="text-sm font-bold text-gray-900">{performance.fps} FPS</p>
            <p className="text-xs text-green-600">{performance.recall}% recall</p>
          </div>

          <div className="bg-white/60 rounded-lg p-2 text-center">
            <Clock className="w-4 h-4 text-blue-600 mx-auto mb-1" />
            <p className="text-xs text-gray-600">Training</p>
            <p className="text-sm font-bold text-gray-900">{cost.time} min</p>
          </div>

          <div className="bg-white/60 rounded-lg p-2 text-center">
            <DollarSign className="w-4 h-4 text-purple-600 mx-auto mb-1" />
            <p className="text-xs text-gray-600">Cost</p>
            <p className="text-sm font-bold text-gray-900">${cost.amount}</p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 mt-4">
          <button className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium py-2 rounded-lg transition-colors">
            Start Training
          </button>
          <button className="px-4 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium py-2 rounded-lg border border-gray-300 transition-colors">
            Adjust
          </button>
        </div>
      </div>

      {/* Alternatives (Collapsible) */}
      {alternatives && alternatives.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer list-none flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            <span className="text-xs font-medium text-gray-600">
              View {alternatives.length} Alternative Strategies
            </span>
            <svg
              className="w-4 h-4 text-gray-400 transition-transform group-open:rotate-180"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </summary>

          <div className="mt-2 space-y-2">
            {alternatives.map((alt, idx) => (
              <AlternativeOption key={idx} data={alt} index={idx} />
            ))}
          </div>
        </details>
      )}
    </motion.div>
  );
}

function AlternativeOption({ data, index }: { data: Alternative; index: number }) {
  const labels = ['Option A', 'Option B', 'Option C'];

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="bg-white border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-colors"
    >
      <div className="flex items-start justify-between mb-2">
        <h5 className="text-sm font-semibold text-gray-700">{labels[index]}: {data.name}</h5>
        <span className="text-xs text-gray-500">${data.cost}</span>
      </div>
      <p className="text-xs text-gray-600 mb-2">{data.description}</p>
      <p className="text-xs text-amber-600 italic">
        <strong>Tradeoff:</strong> {data.tradeoff}
      </p>
    </motion.div>
  );
}