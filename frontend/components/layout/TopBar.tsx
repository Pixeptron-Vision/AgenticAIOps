// components/layout/TopBar.tsx
'use client';

import { useState } from 'react';
import { Bell, Settings, User, DollarSign, Activity } from 'lucide-react';
import { motion } from 'framer-motion';
import { useNotifications } from '@/contexts/NotificationContext';
import { NotificationPanel } from '@/components/notifications/NotificationPanel';
import { UserDropdown } from '@/components/layout/UserDropdown';

interface UserProfile {
  name: string;
  role: string;
}

interface Budget {
  spent: number;
  limit: number;
  remaining: number;
}

interface TopBarProps {
  user: UserProfile;
  budget: Budget;
  onSettingsClick?: () => void;
}

export function TopBar({ user, budget, onSettingsClick }: TopBarProps) {
  const [showNotifications, setShowNotifications] = useState(false);
  const { unreadCount } = useNotifications();

  return (
    <>
    <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      {/* Left: Logo & Title */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg">
          <span className="text-white text-xl font-bold">🤖</span>
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900">AgenticAIOps</h1>
          <p className="text-xs text-gray-500">Intelligent ML Operations Platform</p>
        </div>
      </div>

      {/* Right: User Info & Actions */}
      <div className="flex items-center gap-4">
        {/* System Status */}
        <SystemStatus />

        {/* Budget Indicator */}
        <BudgetIndicator budget={budget} />

        {/* Notifications */}
        <button
          onClick={() => setShowNotifications(!showNotifications)}
          className="relative p-2 text-gray-600 hover:text-gray-900 transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center"
            >
              {unreadCount}
            </motion.span>
          )}
        </button>

        {/* Settings */}
        <button
          onClick={onSettingsClick}
          className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
        >
          <Settings className="w-5 h-5" />
        </button>

        {/* User Profile with Dropdown */}
        <UserDropdown user={user} />
      </div>
    </div>

    {/* Notification Panel */}
    <NotificationPanel
      isOpen={showNotifications}
      onClose={() => setShowNotifications(false)}
    />
    </>
  );
}

function SystemStatus() {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 rounded-lg">
      <motion.div
        animate={{ scale: [1, 1.2, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="w-2 h-2 bg-green-500 rounded-full"
      />
      <span className="text-xs font-medium text-green-700">All Systems Operational</span>
    </div>
  );
}

function BudgetIndicator({ budget }: { budget: Budget }) {
  const percentUsed = (budget.spent / budget.limit) * 100;
  const isLow = percentUsed > 80;

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
      isLow ? 'bg-amber-50' : 'bg-blue-50'
    }`}>
      <DollarSign className={`w-4 h-4 ${isLow ? 'text-amber-600' : 'text-blue-600'}`} />
      <span className={`text-sm font-semibold ${
        isLow ? 'text-amber-700' : 'text-blue-700'
      }`}>
        ${budget.remaining.toFixed(2)}
      </span>
      <span className="text-xs text-gray-500">left</span>
    </div>
  );
}