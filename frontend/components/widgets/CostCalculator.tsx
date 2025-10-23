// components/widgets/CostCalculator.tsx
import { useState } from 'react';
import { DollarSign, TrendingDown, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

interface CostCalculatorProps {
  modelConfig: {
    estimatedTime: number;
  };
}

export function CostCalculator({ modelConfig }: CostCalculatorProps) {
  const [useSpot, setUseSpot] = useState(true);
  const [useCPU, setUseCPU] = useState(false);

  const calculateCost = () => {
    let baseCost = modelConfig.estimatedTime * 0.526; // GPU on-demand

    if (useSpot) baseCost *= 0.3; // 70% savings
    if (useCPU) baseCost *= 0.15; // CPU much cheaper but slower

    return baseCost;
  };

  const savings = modelConfig.estimatedTime * 0.526 - calculateCost();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-4 border border-green-200"
    >
      <div className="flex items-center gap-2 mb-4">
        <DollarSign className="w-5 h-5 text-green-600" />
        <h3 className="text-sm font-bold text-green-900">Cost Estimate</h3>
      </div>

      {/* Options */}
      <div className="space-y-2 mb-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={useSpot}
            onChange={(e) => setUseSpot(e.target.checked)}
            className="rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          <span className="text-sm text-gray-700">Use spot instances (70% savings)</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={useCPU}
            onChange={(e) => setUseCPU(e.target.checked)}
            className="rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          <span className="text-sm text-gray-700">Use CPU workers (slower)</span>
        </label>
      </div>

      {/* Cost Display */}
      <div className="bg-white/60 rounded-lg p-3">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-sm text-gray-600">Estimated Cost</span>
          <motion.span
            key={calculateCost()}
            initial={{ scale: 1.2, color: '#10b981' }}
            animate={{ scale: 1, color: '#111827' }}
            className="text-2xl font-bold text-gray-900"
          >
            ${calculateCost().toFixed(2)}
          </motion.span>
        </div>

        {savings > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-1 text-xs text-green-600 font-medium"
          >
            <TrendingDown className="w-3 h-3" />
            Saving ${savings.toFixed(2)} vs on-demand GPU
          </motion.div>
        )}
      </div>

      {useCPU && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-3 flex items-start gap-2 p-2 bg-amber-50 rounded-lg"
        >
          <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-amber-700">
            Training time will increase by ~4x on CPU
          </p>
        </motion.div>
      )}
    </motion.div>
  );
}