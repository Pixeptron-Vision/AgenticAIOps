// components/chat/AgentMessage.tsx
import { motion } from 'framer-motion';
import { Sparkles, Brain, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { ConstraintAnalysisCard } from '@/components/cards/ConstraintAnalysisCard';
import { RecommendationCard } from '@/components/cards/RecommendationCard';
import { JobStatusCard } from '@/components/cards/JobStatusCard';
import { formatTimestamp } from '@/lib/utils';
import { useState } from 'react';

export function AgentMessage({ message, type = 'text', data, timestamp, thinkingSteps }: { message?: string; type?: string; data?: any; timestamp?: string; thinkingSteps?: string[] }) {
  const [showThinking, setShowThinking] = useState(false);
  const getIcon = () => {
    const msg = message || '';
    if (msg.includes('Analyzing')) return <Brain className="w-4 h-4" />;
    if (msg.includes('Complete')) return <CheckCircle className="w-4 h-4" />;
    if (msg.includes('Issue')) return <AlertCircle className="w-4 h-4" />;
    return <Sparkles className="w-4 h-4" />;
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex justify-start mb-4"
    >
      <div className="max-w-[85%]">
        {/* Agent Avatar */}
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-medium text-gray-700">Agent</span>
          {getIcon()}
        </div>

        {/* Message Content */}
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
            {message}
          </p>

          {/* Rich Content Cards */}
          {type === 'constraint_analysis' && (
            <ConstraintAnalysisCard data={data} />
          )}
          {type === 'recommendation' && (
            <RecommendationCard data={data} />
          )}
          {type === 'job_status' && (
            <JobStatusCard data={data} />
          )}

          {/* Thinking Process (Collapsible) */}
          {thinkingSteps && thinkingSteps.length > 0 && (
            <div className="mt-3 border-t border-gray-100 pt-3">
              <button
                onClick={() => setShowThinking(!showThinking)}
                className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                {showThinking ? (
                  <ChevronDown className="w-3.5 h-3.5" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5" />
                )}
                <Brain className="w-3.5 h-3.5" />
                <span className="font-medium">
                  {showThinking ? 'Hide reasoning' : `View reasoning (${thinkingSteps.length} steps)`}
                </span>
              </button>

              {showThinking && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-2 space-y-1.5"
                >
                  {thinkingSteps.map((step, idx) => (
                    <div
                      key={idx}
                      className="flex gap-2 text-xs text-gray-600 bg-gray-50 rounded px-2 py-1.5"
                    >
                      <span className="text-gray-400 font-mono">{idx + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </motion.div>
              )}
            </div>
          )}
        </div>

        <p className="text-xs text-gray-400 mt-1">{formatTimestamp(timestamp)}</p>
      </div>
    </motion.div>
  );
}