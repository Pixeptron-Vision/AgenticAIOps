'use client';

import { MessageSquare, DollarSign, Clock, Archive } from 'lucide-react';
import { motion } from 'framer-motion';
import { SessionSummary } from '@/types/session';

interface SessionListItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
  onArchive?: (sessionId: string) => void;
}

export function SessionListItem({ session, isActive, onClick, onArchive }: SessionListItemProps) {
  const percentUsed = (session.budget_spent / session.budget_limit) * 100;

  // Budget color based on usage
  const getBudgetColor = () => {
    if (percentUsed >= 95) return 'text-red-600';
    if (percentUsed >= 80) return 'text-orange-600';
    if (percentUsed >= 50) return 'text-yellow-600';
    return 'text-green-600';
  };

  // Format timestamp
  const formatTime = (timestamp?: number) => {
    if (!timestamp) return 'No messages';
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const handleArchive = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering onClick
    onArchive?.(session.session_id);
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg transition-all group relative ${
        isActive
          ? 'bg-blue-50 border-2 border-blue-500 shadow-sm'
          : 'bg-white border border-gray-200 hover:border-gray-300 hover:shadow-sm'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
          <span className={`text-sm font-medium truncate ${isActive ? 'text-blue-900' : 'text-gray-900'}`}>
            {session.session_name}
          </span>
        </div>

        {/* Archive button - visible on hover */}
        {onArchive && (
          <button
            onClick={handleArchive}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-gray-200 rounded"
            title="Archive session"
          >
            <Archive className="w-3.5 h-3.5 text-gray-500 hover:text-gray-700" />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-gray-500">
          <Clock className="w-3 h-3" />
          <span>{formatTime(session.last_message_at)}</span>
        </div>
        <div className={`flex items-center gap-1 font-medium ${getBudgetColor()}`}>
          <DollarSign className="w-3 h-3" />
          <span>{(session.budget_limit - session.budget_spent).toFixed(1)}</span>
        </div>
      </div>

      {session.message_count > 0 && (
        <div className="mt-2 text-xs text-gray-500">
          {session.message_count} message{session.message_count !== 1 ? 's' : ''}
        </div>
      )}
    </motion.button>
  );
}
