import { motion, AnimatePresence } from 'framer-motion';
import { X, Save } from 'lucide-react';
import { useState } from 'react';
import { useLocalStorage } from '@/hooks/useLocalStorage';

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsDialog({ isOpen, onClose }: SettingsDialogProps) {
  const [sessionBudget, setSessionBudget] = useLocalStorage('session_budget', 50);
  const [enableNotifications, setEnableNotifications] = useLocalStorage('enable_notifications', true);
  const [enableSounds, setEnableSounds] = useLocalStorage('enable_sounds', true);
  const [theme, setTheme] = useLocalStorage('theme', 'light');

  const handleSave = () => {
    // Settings are auto-saved via localStorage
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Settings</h2>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Budget Settings */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Budget</h3>
                <div className="space-y-2">
                  <label className="block text-sm text-gray-700">
                    Default Session Budget (USD)
                  </label>
                  <input
                    type="number"
                    value={sessionBudget}
                    onChange={(e) => setSessionBudget(Number(e.target.value))}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    min="0"
                    step="10"
                  />
                  <p className="text-xs text-gray-500">
                    Agent will alert you when approaching this limit
                  </p>
                </div>
              </div>

              {/* Notifications */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Notifications</h3>
                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={enableNotifications}
                      onChange={(e) => setEnableNotifications(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Enable notifications</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={enableSounds}
                      onChange={(e) => setEnableSounds(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Enable sound alerts</span>
                  </label>
                </div>
              </div>

              {/* Theme */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Appearance</h3>
                <div className="grid grid-cols-2 gap-3">
                  {['light', 'dark'].map((t) => (
                    <button
                      key={t}
                      onClick={() => setTheme(t)}
                      className={`p-3 rounded-lg border-2 transition-colors ${
                        theme === t
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="text-sm font-medium text-gray-900 capitalize">
                        {t}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Advanced */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Advanced</h3>
                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Enable debug mode</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      defaultChecked
                    />
                    <span className="text-sm text-gray-700">Auto-save conversation history</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}