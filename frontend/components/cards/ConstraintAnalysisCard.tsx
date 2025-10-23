import { motion } from 'framer-motion';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { ConstraintAnalysis } from '@/types/agent';

export function ConstraintAnalysisCard({ data }: { data: ConstraintAnalysis }) {
  const { dataset, compute, challenges } = data;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 p-4 bg-gradient-to-br from-slate-50 to-gray-50 rounded-xl border border-gray-200"
    >
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Constraint Analysis
      </h4>

      {/* Dataset Check */}
      <div className="flex items-start gap-3 mb-2">
        <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-gray-800">Dataset: {dataset.name}</p>
          <p className="text-xs text-gray-500">
            {dataset.samples.toLocaleString()} samples, {dataset.classes} classes
          </p>
        </div>
      </div>

      {/* Compute Check */}
      <div className="flex items-start gap-3 mb-2">
        <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-gray-800">
            Compute: {compute.available} GPU workers available
          </p>
          <p className="text-xs text-gray-500">
            Current usage: {compute.used}/{compute.total}
          </p>
        </div>
      </div>

      {/* Challenge */}
      {challenges && challenges.length > 0 && (
        <div className="flex items-start gap-3 p-2 bg-amber-50 rounded-lg mt-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-900">Challenge</p>
            <p className="text-xs text-amber-700">{challenges[0]}</p>
          </div>
        </div>
      )}
    </motion.div>
  );
}