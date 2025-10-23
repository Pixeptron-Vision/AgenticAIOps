'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';
import { useNotifications } from '@/contexts/NotificationContext';

export function ToastContainer() {
  const { notifications, clearNotification } = useNotifications();

  // Only show last 3 unread notifications as toasts
  const toasts = notifications.filter(n => !n.read).slice(0, 3);

  return (
    <div className="fixed top-20 right-6 z-50 space-y-3">
      <AnimatePresence>
        {toasts.map((notification) => (
          <Toast
            key={notification.id}
            notification={notification}
            onClose={() => clearNotification(notification.id)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

function Toast({ notification, onClose }: { notification: any; onClose: () => void }) {
  const icons = {
    success: <CheckCircle className="w-5 h-5 text-green-600" />,
    error: <XCircle className="w-5 h-5 text-red-600" />,
    warning: <AlertCircle className="w-5 h-5 text-amber-600" />,
    info: <Info className="w-5 h-5 text-blue-600" />,
  };

  const styles = {
    success: 'bg-green-50 border-green-200',
    error: 'bg-red-50 border-red-200',
    warning: 'bg-amber-50 border-amber-200',
    info: 'bg-blue-50 border-blue-200',
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 100, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.9 }}
      className={`w-96 p-4 rounded-xl border-2 shadow-lg ${styles[notification.type]}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {icons[notification.type]}
        </div>

        <div className="flex-1">
          <h4 className="font-semibold text-gray-900 mb-1">
            {notification.title}
          </h4>
          <p className="text-sm text-gray-700">
            {notification.message}
          </p>
          {notification.metadata && (
            <div className="mt-2 text-xs text-gray-600">
              {notification.metadata.cost && (
                <span className="mr-3">Cost: ${notification.metadata.cost.toFixed(2)}</span>
              )}
              {notification.metadata.newStatus && (
                <span>Status: {notification.metadata.newStatus}</span>
              )}
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="flex-shrink-0 p-1 hover:bg-white/50 rounded-lg transition-colors"
        >
          <X className="w-4 h-4 text-gray-600" />
        </button>
      </div>
    </motion.div>
  );
}
