// components/dialogs/ConstraintNegotiation.tsx
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, CheckCircle } from 'lucide-react';

interface Conflict {
  constraint: string;
  required: string;
  achievable: string;
}

interface Alternative {
  name: string;
  description: string;
  tradeoff: string;
}

interface ConstraintNegotiationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  conflicts: Conflict[];
  alternatives: Alternative[];
  onSelect: (alternative: Alternative) => void;
}

export function ConstraintNegotiationDialog({
  isOpen,
  onClose,
  conflicts,
  alternatives,
  onSelect,
}: ConstraintNegotiationDialogProps) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        />

        {/* Dialog */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="p-6 bg-gradient-to-r from-amber-50 to-orange-50 border-b border-amber-200">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-amber-500 rounded-lg flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Constraint Conflict Detected
                  </h2>
                  <p className="text-sm text-gray-600 mt-1">
                    Your requirements conflict. Let&apos;s find a solution together.
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            {/* Conflicts */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                Identified Conflicts:
              </h3>
              <div className="space-y-2">
                {conflicts.map((conflict, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg"
                  >
                    <X className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-red-900">
                        {conflict.constraint}
                      </p>
                      <p className="text-xs text-red-700 mt-1">
                        Required: {conflict.required} | Achievable: {conflict.achievable}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Alternatives */}
            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                Proposed Alternatives:
              </h3>
              <div className="space-y-3">
                {alternatives.map((alt, idx) => (
                  <motion.button
                    key={idx}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + idx * 0.1 }}
                    onClick={() => onSelect(alt)}
                    className="w-full text-left p-4 bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-xl hover:border-green-300 hover:shadow-md transition-all group"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-green-600" />
                        <h4 className="text-sm font-bold text-green-900">
                          {alt.name}
                        </h4>
                      </div>
                      {idx === 0 && (
                        <span className="px-2 py-1 bg-green-600 text-white text-xs font-semibold rounded-full">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 mb-2">{alt.description}</p>
                    <p className="text-xs text-amber-700 italic">
                      <strong>Tradeoff:</strong> {alt.tradeoff}
                    </p>
                  </motion.button>
                ))}
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}