'use client';

import { useState, useEffect } from 'react';
import { X, DollarSign, Globe, MessageSquare, Archive, AlertTriangle, User } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { BudgetInfo } from '@/types/budget';
import { SessionSummary } from '@/types/session';
import { api } from '@/lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  globalBudget: BudgetInfo | null;
  sessionBudget: BudgetInfo | null;
  sessions: SessionSummary[];
  onUpdateGlobalBudget: (limit: number) => Promise<void>;
  onUpdateSessionBudget: (sessionId: string, limit: number) => Promise<void>;
}

type SettingsSection = 'user' | 'budgets' | 'archived';

export function SettingsModal({
  isOpen,
  onClose,
  globalBudget,
  sessionBudget,
  sessions,
  onUpdateGlobalBudget,
  onUpdateSessionBudget,
}: SettingsModalProps) {
  // Section navigation
  const [activeSection, setActiveSection] = useState<SettingsSection>('user');

  // User settings state
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [savingUser, setSavingUser] = useState(false);

  // Budget settings state
  const [globalLimit, setGlobalLimit] = useState('');
  const [sessionLimit, setSessionLimit] = useState('');
  const [selectedSessionId, setSelectedSessionId] = useState<string>('');
  const [selectedSessionBudget, setSelectedSessionBudget] = useState<BudgetInfo | null>(null);
  const [loadingSessionBudget, setLoadingSessionBudget] = useState(false);

  // Archived sessions state
  const [archivedSessions, setArchivedSessions] = useState<SessionSummary[]>([]);
  const [loadingArchived, setLoadingArchived] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // General state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Load user info from localStorage on mount
  useEffect(() => {
    const savedName = localStorage.getItem('user_name') || '';
    const savedEmail = localStorage.getItem('user_email') || '';
    setUserName(savedName);
    setUserEmail(savedEmail);
  }, [isOpen]);

  useEffect(() => {
    if (globalBudget) {
      setGlobalLimit(globalBudget.limit.toString());
    }
  }, [globalBudget]);

  // Load selected session's budget when selection changes
  useEffect(() => {
    if (!selectedSessionId) return;

    const loadSessionBudget = async () => {
      setLoadingSessionBudget(true);
      try {
        const budget = await api.getSessionBudget(selectedSessionId);
        setSelectedSessionBudget(budget);
        setSessionLimit(budget.limit.toString());
      } catch (err) {
        setError('Failed to load session budget');
      } finally {
        setLoadingSessionBudget(false);
      }
    };

    loadSessionBudget();
  }, [selectedSessionId]);

  // Initialize selected session when modal opens
  useEffect(() => {
    if (isOpen && sessions.length > 0 && !selectedSessionId) {
      // Default to first session or current session if available
      const defaultSession = sessionBudget?.session_id || sessions[0].session_id;
      setSelectedSessionId(defaultSession);
    }
  }, [isOpen, sessions, sessionBudget, selectedSessionId]);

  // Load archived sessions when modal opens and archived section is selected
  useEffect(() => {
    if (isOpen && activeSection === 'archived') {
      loadArchivedSessions();
    }
  }, [isOpen, activeSection]);

  const loadArchivedSessions = async () => {
    setLoadingArchived(true);
    try {
      const allSessions = await api.getSessions(true); // includeArchived = true
      const archived = allSessions.filter(s => s.is_archived);
      setArchivedSessions(archived);
    } catch (err) {
      setError('Failed to load archived sessions');
    } finally {
      setLoadingArchived(false);
    }
  };

  const handleSaveUserInfo = async () => {
    setSavingUser(true);
    setError(null);
    try {
      // Save to localStorage
      localStorage.setItem('user_name', userName);
      localStorage.setItem('user_email', userEmail);
      setSuccess('User information saved successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Failed to save user information');
    } finally {
      setSavingUser(false);
    }
  };

  const handleSaveGlobal = async () => {
    const limit = parseFloat(globalLimit);
    if (isNaN(limit) || limit <= 0) {
      setError('Please enter a valid budget limit');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onUpdateGlobalBudget(limit);
      setSuccess('Global budget updated successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Failed to update global budget');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSession = async () => {
    if (!selectedSessionId) {
      setError('Please select a session');
      return;
    }

    const limit = parseFloat(sessionLimit);
    if (isNaN(limit) || limit <= 0) {
      setError('Please enter a valid budget limit');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onUpdateSessionBudget(selectedSessionId, limit);
      setSuccess('Session budget updated successfully');
      setTimeout(() => setSuccess(null), 3000);

      // Reload the budget to reflect changes
      const budget = await api.getSessionBudget(selectedSessionId);
      setSelectedSessionBudget(budget);
    } catch (err) {
      setError('Failed to update session budget');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    setDeleting(true);
    setError(null);
    try {
      await api.deleteSessionPermanent(sessionId);
      setSuccess('Session permanently deleted');
      setTimeout(() => setSuccess(null), 3000);

      // Reload archived sessions
      await loadArchivedSessions();

      // Close confirmation dialog
      setSessionToDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-40"
          />

          {/* Modal - Two Panel Layout */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex">
              {/* LEFT PANEL - Navigation Sidebar */}
              <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-bold text-gray-900">Settings</h2>
                </div>

                {/* Navigation Items */}
                <nav className="flex-1 p-4 space-y-1">
                  <button
                    onClick={() => setActiveSection('user')}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left ${
                      activeSection === 'user'
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`}
                  >
                    <User className="w-5 h-5" />
                    <span className="text-sm font-medium">User Profile</span>
                  </button>

                  <button
                    onClick={() => setActiveSection('budgets')}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left ${
                      activeSection === 'budgets'
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`}
                  >
                    <DollarSign className="w-5 h-5" />
                    <span className="text-sm font-medium">Budgets</span>
                  </button>

                  <button
                    onClick={() => setActiveSection('archived')}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left ${
                      activeSection === 'archived'
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`}
                  >
                    <Archive className="w-5 h-5" />
                    <div className="flex-1 flex items-center justify-between">
                      <span className="text-sm font-medium">Archived Sessions</span>
                      {archivedSessions.length > 0 && (
                        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
                          {archivedSessions.length}
                        </span>
                      )}
                    </div>
                  </button>
                </nav>
              </div>

              {/* RIGHT PANEL - Content Area */}
              <div className="flex-1 flex flex-col">
                {/* Header with Close Button */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                  <h3 className="text-2xl font-bold text-gray-900">
                    {activeSection === 'user' ? 'User Profile' : activeSection === 'budgets' ? 'Budget Management' : 'Archived Sessions'}
                  </h3>
                  <button
                    onClick={onClose}
                    className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <X className="w-6 h-6" />
                  </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                  {/* Error/Success Messages */}
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
                    >
                      {error}
                    </motion.div>
                  )}
                  {success && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm"
                    >
                      {success}
                    </motion.div>
                  )}

                  {/* USER PROFILE SECTION */}
                  {activeSection === 'user' && (
                    <div className="space-y-6">
                      <div className="flex items-center gap-3">
                        <div className="p-3 bg-blue-100 rounded-lg">
                          <User className="w-6 h-6 text-blue-600" />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">Personal Information</h3>
                          <p className="text-sm text-gray-500">Manage your profile details</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Full Name
                          </label>
                          <input
                            type="text"
                            value={userName}
                            onChange={(e) => setUserName(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="Enter your full name"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Email Address
                          </label>
                          <input
                            type="email"
                            value={userEmail}
                            onChange={(e) => setUserEmail(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="Enter your email address"
                          />
                        </div>

                        <div className="pt-2">
                          <button
                            onClick={handleSaveUserInfo}
                            disabled={savingUser}
                            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {savingUser ? 'Saving...' : 'Save Changes'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* BUDGETS SECTION */}
                  {activeSection === 'budgets' && (
                    <div className="space-y-8">
                      {/* Global Budget */}
                      <div className="space-y-4">
                        <div className="flex items-center gap-3">
                          <div className="p-3 bg-blue-100 rounded-lg">
                            <Globe className="w-6 h-6 text-blue-600" />
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900">Global Budget</h3>
                            <p className="text-sm text-gray-500">Total budget across all sessions</p>
                          </div>
                        </div>

                        <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-600">Current Limit:</span>
                            <span className="font-semibold">${globalBudget?.limit.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-600">Spent:</span>
                            <span className="font-semibold text-red-600">${globalBudget?.spent.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-600">Remaining:</span>
                            <span className="font-semibold text-green-600">${globalBudget?.remaining.toFixed(2)}</span>
                          </div>
                        </div>

                        <div className="flex gap-2">
                          <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              New Limit ($)
                            </label>
                            <input
                              type="number"
                              step="0.01"
                              value={globalLimit}
                              onChange={(e) => setGlobalLimit(e.target.value)}
                              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="Enter new limit"
                            />
                          </div>
                          <div className="flex items-end">
                            <button
                              onClick={handleSaveGlobal}
                              disabled={saving}
                              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {saving ? 'Saving...' : 'Update'}
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Session Budget */}
                      {sessions.length > 0 && (
                        <>
                          <div className="h-px bg-gray-200" />
                          <div className="space-y-4">
                            <div className="flex items-center gap-3">
                              <div className="p-3 bg-purple-100 rounded-lg">
                                <MessageSquare className="w-6 h-6 text-purple-600" />
                              </div>
                              <div>
                                <h3 className="text-lg font-semibold text-gray-900">Session Budget</h3>
                                <p className="text-sm text-gray-500">Select a session to manage its budget</p>
                              </div>
                            </div>

                            {/* Session Selector */}
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                Select Session
                              </label>
                              <select
                                value={selectedSessionId}
                                onChange={(e) => setSelectedSessionId(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                              >
                                {sessions.map((session) => (
                                  <option key={session.session_id} value={session.session_id}>
                                    {session.session_name}
                                  </option>
                                ))}
                              </select>
                            </div>

                            {loadingSessionBudget ? (
                              <div className="text-center py-4 text-sm text-gray-500">
                                Loading session budget...
                              </div>
                            ) : selectedSessionBudget ? (
                              <>
                                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                                  <div className="flex justify-between text-sm">
                                    <span className="text-gray-600">Current Limit:</span>
                                    <span className="font-semibold">${selectedSessionBudget.limit.toFixed(2)}</span>
                                  </div>
                                  <div className="flex justify-between text-sm">
                                    <span className="text-gray-600">Spent:</span>
                                    <span className="font-semibold text-red-600">${selectedSessionBudget.spent.toFixed(2)}</span>
                                  </div>
                                  <div className="flex justify-between text-sm">
                                    <span className="text-gray-600">Remaining:</span>
                                    <span className="font-semibold text-green-600">${selectedSessionBudget.remaining.toFixed(2)}</span>
                                  </div>
                                </div>

                                <div className="flex gap-2">
                                  <div className="flex-1">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                      New Limit ($)
                                    </label>
                                    <input
                                      type="number"
                                      step="0.01"
                                      value={sessionLimit}
                                      onChange={(e) => setSessionLimit(e.target.value)}
                                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                                      placeholder="Enter new limit"
                                    />
                                  </div>
                                  <div className="flex items-end">
                                    <button
                                      onClick={handleSaveSession}
                                      disabled={saving}
                                      className="px-6 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      {saving ? 'Saving...' : 'Update'}
                                    </button>
                                  </div>
                                </div>
                              </>
                            ) : null}
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* ARCHIVED SESSIONS SECTION */}
                  {activeSection === 'archived' && (
                    <div className="space-y-4">
                      {loadingArchived ? (
                        <div className="text-center py-12 text-sm text-gray-500">
                          Loading archived sessions...
                        </div>
                      ) : archivedSessions.length === 0 ? (
                        <div className="text-center py-12">
                          <Archive className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                          <p className="text-gray-500">No archived sessions</p>
                          <p className="text-sm text-gray-400 mt-1">
                            Archived sessions will appear here
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {archivedSessions.map((session) => (
                            <div
                              key={session.session_id}
                              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <h4 className="font-medium text-gray-900 mb-1">
                                    {session.session_name}
                                  </h4>
                                  <div className="flex items-center gap-4 text-sm text-gray-500">
                                    <span>{session.message_count} messages</span>
                                    <span>•</span>
                                    <span>${session.budget_spent.toFixed(2)} spent</span>
                                  </div>
                                </div>
                                <button
                                  onClick={() => setSessionToDelete(session.session_id)}
                                  className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                >
                                  Delete
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
                  <button
                    onClick={onClose}
                    className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Delete Confirmation Dialog */}
          {sessionToDelete && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4"
              onClick={() => !deleting && setSessionToDelete(null)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-red-100 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-red-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Delete Session Permanently?
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                      This action cannot be undone. All messages and data associated with this
                      session will be permanently deleted.
                    </p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => handleDeleteSession(sessionToDelete)}
                        disabled={deleting}
                        className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {deleting ? 'Deleting...' : 'Delete Permanently'}
                      </button>
                      <button
                        onClick={() => setSessionToDelete(null)}
                        disabled={deleting}
                        className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </>
      )}
    </AnimatePresence>
  );
}
