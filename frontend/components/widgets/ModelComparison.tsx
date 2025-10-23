// components/widgets/ModelComparison.tsx
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Model } from '@/types/models';

type ConstraintKey = 'fps' | 'accuracy' | 'size_mb' | 'latency_ms';

interface ModelComparisonProps {
  models: (Model & { params: string, cost: number, fps: number, latency_ms: number, size_mb: number, accuracy: number })[];
  constraints: {
    min_accuracy: number;
    max_latency: number;
    max_size: number;
  };
}

export function ModelComparison({ models, constraints }: ModelComparisonProps) {
  const checkConstraint = (modelValue: number, constraintValue: number, constraintType: 'min' | 'max') => {
    if (constraintType === 'min' && modelValue >= constraintValue) return 'pass';
    if (constraintType === 'max' && modelValue <= constraintValue) return 'pass';
    
    const diff = Math.abs(modelValue - constraintValue);
    const threshold = constraintValue * 0.1; // Within 10%
    if (diff <= threshold) return 'warning';
    
    return 'fail';
  };

  const getStatusIcon = (status: 'pass' | 'warning' | 'fail') => {
    if (status === 'pass') return <CheckCircle className="w-4 h-4 text-green-500" />;
    if (status === 'warning') return <AlertCircle className="w-4 h-4 text-amber-500" />;
    return <XCircle className="w-4 h-4 text-red-500" />;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl border border-gray-200 overflow-hidden"
    >
      <div className="p-4 bg-gray-50 border-b border-gray-200">
        <h3 className="text-sm font-bold text-gray-900">Model Comparison</h3>
        <p className="text-xs text-gray-600 mt-1">
          Comparing {models.length} candidates against your constraints
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">
                Model
              </th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600">
                Accuracy
              </th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600">
                Latency
              </th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600">
                Size
              </th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600">
                Cost
              </th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600">
                Overall
              </th>
            </tr>
          </thead>
                    <tbody className="divide-y divide-gray-200">
            {models.map((model, idx) => {
              const accuracyStatus = checkConstraint(model.accuracy, constraints.min_accuracy, 'min');
              const latencyStatus = checkConstraint(model.latency_ms, constraints.max_latency, 'max');
              const sizeStatus = checkConstraint(model.size_mb, constraints.max_size, 'max');
              
              const overallPass = [accuracyStatus, latencyStatus, sizeStatus].every(s => s === 'pass');

              return (
                <motion.tr
                  key={model.name}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className={`hover:bg-gray-50 ${overallPass ? 'bg-green-50/30' : ''}`}
                >
                  <td className="px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{model.name}</p>
                      <p className="text-xs text-gray-500">{model.params}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {getStatusIcon(accuracyStatus)}
                      <span className="text-sm font-medium">{model.accuracy}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {getStatusIcon(latencyStatus)}
                      <span className="text-sm font-medium">{model.latency_ms}ms</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {getStatusIcon(sizeStatus)}
                      <span className="text-sm font-medium">{model.size_mb}MB</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-sm font-medium text-gray-900">${model.cost}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {overallPass ? (
                      <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded-full">
                        ✓ Meets All
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs font-semibold rounded-full">
                        Partial
                      </span>
                    )}
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Target Constraints Footer */}
      <div className="p-4 bg-gray-50 border-t border-gray-200">
        <p className="text-xs font-semibold text-gray-600 mb-2">Target Constraints:</p>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(constraints) as (keyof typeof constraints)[]).map((key) => (
            <span
              key={key}
              className="px-2 py-1 bg-white border border-gray-200 rounded text-xs text-gray-700"
            >
              {key}: <span className="font-semibold">{constraints[key]}</span>
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  );
}