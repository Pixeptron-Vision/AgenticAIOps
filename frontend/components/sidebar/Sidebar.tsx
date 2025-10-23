// components/sidebar/Sidebar.tsx
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home,
  Briefcase,
  Target,
  FolderOpen,
  BarChart3,
  Zap,
  Plus,
} from 'lucide-react';
import { ActiveJobsList } from './ActiveJobsList';
import { QuickActions } from './QuickActions';
import { BudgetDisplay } from './BudgetDisplay';
import { CreateSessionModal } from '../session/CreateSessionModal';
import { SessionsPanel } from '../session/SessionsPanel';
import { Job } from '@/types/jobs';
import { SessionSummary } from '@/types/session';

interface SidebarProps {
  activeJobs?: Job[];
  budget?: { spent: number; limit: number; remaining: number };
  sessions?: SessionSummary[];
  currentSessionId?: string | null;
  onCreateSession?: (name: string, budget: number) => Promise<void>;
  onSelectSession?: (sessionId: string) => void;
  onArchiveSession?: (sessionId: string) => void;
}

export function Sidebar({
  activeJobs = [],
  budget,
  sessions = [],
  currentSessionId = null,
  onCreateSession = async () => {},
  onSelectSession = () => {},
  onArchiveSession = () => {},
}: SidebarProps) {
  const [showNewSessionModal, setShowNewSessionModal] = useState(false);

  const handleCreateSession = async (name: string, budget: number) => {
    await onCreateSession(name, budget);
    setShowNewSessionModal(false);
  };

  const navItems = [
    { icon: Home, label: 'Home', href: '/chat', isButton: false },
    { icon: Plus, label: 'New Session', onClick: () => setShowNewSessionModal(true), isButton: true },
    { icon: Briefcase, label: 'Jobs', href: '/jobs', badge: activeJobs.length, isButton: false },
    { icon: Target, label: 'Models', href: '/models', isButton: false },
    { icon: FolderOpen, label: 'Data', href: '/data', isButton: false },
    { icon: BarChart3, label: 'Metrics', href: '/metrics', isButton: false },
  ];

  return (
    <>
      <motion.div
        initial={{ x: -300 }}
        animate={{ x: 0 }}
        className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col h-full"
      >
        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => (
            <NavItem key={item.label} {...item} />
          ))}
        </nav>

      <div className="h-px bg-gray-200 mx-4" />

      {/* Sessions Panel */}
      <div className="p-4">
        <SessionsPanel
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={onSelectSession}
          onArchiveSession={onArchiveSession}
        />
      </div>

      <div className="h-px bg-gray-200 mx-4" />

      {/* Quick Actions */}
      <div className="p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Quick Actions
        </h3>
        <QuickActions />
      </div>

      <div className="h-px bg-gray-200 mx-4" />

      {/* Active Jobs */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Active Jobs ({activeJobs.length})
          </h3>
          {activeJobs.length > 0 && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
              className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full"
            />
          )}
        </div>
        <ActiveJobsList jobs={activeJobs} />
      </div>

      <div className="h-px bg-gray-200 mx-4" />

      {/* Budget Display - Session Budget */}
      <BudgetDisplay spent={budget?.spent} limit={budget?.limit} />
    </motion.div>

      {/* New Session Modal */}
      <CreateSessionModal
        isOpen={showNewSessionModal}
        onClose={() => setShowNewSessionModal(false)}
        onCreate={handleCreateSession}
      />
    </>
  );
}

function NavItem({ icon: Icon, label, href, active, badge, isButton, onClick }: { icon: any; label: string; href?: string; active?: boolean; badge?: number; isButton?: boolean; onClick?: () => void }) {
  const baseClass = "flex items-center gap-3 px-3 py-2 rounded-lg transition-colors relative";
  const stateClass = active ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900';

  if (isButton) {
    return (
      <button onClick={onClick} className={`${baseClass} ${stateClass} w-full text-left`}>
        <Icon className="w-5 h-5" />
        <span className="text-sm font-medium">{label}</span>
      </button>
    );
  }

  return (
    <a href={href} className={`${baseClass} ${stateClass}`}>
      <Icon className="w-5 h-5" />
      <span className="text-sm font-medium">{label}</span>
      {badge && badge > 0 && (
        <span className="absolute right-2 top-2 w-5 h-5 bg-blue-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
          {badge}
        </span>
      )}
    </a>
  );
}