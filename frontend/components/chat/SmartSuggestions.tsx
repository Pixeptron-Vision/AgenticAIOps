// components/chat/SmartSuggestions.tsx
import { motion } from 'framer-motion';
import { Sparkles, Zap, Target, Database } from 'lucide-react';

const suggestions = [
  {
    icon: Target,
    text: 'Train object detection model',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    icon: Zap,
    text: 'Deploy sentiment analysis API',
    color: 'from-purple-500 to-pink-500',
  },
  {
    icon: Database,
    text: 'Upload and version dataset',
    color: 'from-green-500 to-emerald-500',
  },
  {
    icon: Sparkles,
    text: 'Check training job status',
    color: 'from-orange-500 to-red-500',
  },
];

export function SmartSuggestions({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className="text-xs font-medium text-gray-500 self-center">
        Try:
      </span>
      {suggestions.map((suggestion, idx) => {
        const Icon = suggestion.icon;
        return (
          <motion.button
            key={idx}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: idx * 0.1 }}
            onClick={() => onSelect(suggestion.text)}
            className="group flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-full hover:border-gray-300 hover:shadow-sm transition-all text-sm"
          >
            <div className={`p-1 rounded-full bg-gradient-to-r ${suggestion.color}`}>
              <Icon className="w-3 h-3 text-white" />
            </div>
            <span className="text-gray-700 group-hover:text-gray-900">
              {suggestion.text}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}