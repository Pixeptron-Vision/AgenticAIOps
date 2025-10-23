// components/chat/UserMessage.tsx
import { motion } from 'framer-motion';
import { formatTimestamp } from '@/lib/utils';

interface UserMessageProps {
  message: string;
  timestamp: string;
}

export function UserMessage({ message, timestamp }: UserMessageProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex justify-end mb-4"
    >
      <div className="max-w-[70%]">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-lg">
          <p className="text-sm leading-relaxed">{message}</p>
        </div>
        <p className="text-xs text-gray-400 mt-1 text-right">{formatTimestamp(timestamp)}</p>
      </div>
    </motion.div>
  );
}