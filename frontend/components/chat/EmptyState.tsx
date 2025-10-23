// components/chat/EmptyState.tsx
import { motion } from 'framer-motion';
import { Sparkles, Zap, Target, TrendingUp } from 'lucide-react';

const features = [
  {
    icon: Target,
    title: 'Smart Model Selection',
    description: 'I analyze your constraints and recommend optimal architectures',
  },
  {
    icon: Zap,
    title: 'Automatic Optimization',
    description: 'From LoRA to quantization, I handle all the complexity',
  },
  {
    icon: TrendingUp,
    title: 'Cost-Aware Training',
    description: 'I track your budget and suggest optimizations to save money',
  },
];

export function EmptyState({ onQuickStart }: { onQuickStart: (text: string) => void }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-2xl text-center"
      >
        {/* Hero */}
        <motion.div
          animate={{
            rotate: [0, 10, -10, 0],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="w-24 h-24 mx-auto mb-6 bg-gradient-to-br from-purple-500 via-pink-500 to-blue-500 rounded-3xl flex items-center justify-center shadow-2xl"
        >
          <Sparkles className="w-12 h-12 text-white" />
        </motion.div>

        <h2 className="text-3xl font-bold text-gray-900 mb-3">
          Welcome to AgenticAIOps
        </h2>
        <p className="text-lg text-gray-600 mb-8">
          Your intelligent assistant for training, optimizing, and deploying ML models.
          Just tell me what you need, and I&apos;ll handle the rest.
        </p>

        {/* Features Grid */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {features.map((feature, idx) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className="p-4 bg-white rounded-xl border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all"
              >
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center mb-3 mx-auto">
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900 mb-1">
                  {feature.title}
                </h3>
                <p className="text-xs text-gray-600">{feature.description}</p>
              </motion.div>
            );
          })}
        </div>

        {/* Quick Start Examples */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-500 mb-3">
            Quick start examples:
          </p>
          {[
            'Train an object detection model for defect detection',
            'Deploy a sentiment analysis API with <30ms latency',
            'Optimize my model for edge deployment on Jetson Nano',
          ].map((example, idx) => (
            <motion.button
              key={idx}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + idx * 0.1 }}
              onClick={() => onQuickStart(example)}
              className="w-full p-3 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg text-left text-sm text-gray-700 transition-colors group"
            >
              <span className="group-hover:text-blue-600 transition-colors">
                &ldquo;{example}&rdquo;
              </span>
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}