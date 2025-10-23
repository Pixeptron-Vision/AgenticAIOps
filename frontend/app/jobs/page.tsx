'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Briefcase, Play, Pause, Trash2, ExternalLink, RefreshCw, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { Job } from '@/types/jobs';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';
import { useNotifications } from '@/contexts/NotificationContext';

export default function JobsPage() {
  // Session management
  const { currentSession, sessions } = useSession(true);

  // Get session budget (not global budget)
  const { sessionBudget } = useBudget(currentSession?.session_id);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'active' | 'succeeded' | 'failed'>('all');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const { addNotification } = useNotifications();
  const previousJobsRef = useRef<Map<string, Job>>(new Map());

  // Budget display - fallback to defaults if not loaded
  const budget = sessionBudget || { spent: 0, limit: 50, remaining: 50 };

  useEffect(() => {
    loadJobs();
  }, []);

  // Auto-refresh when there are active jobs
  useEffect(() => {
    const hasActiveJobs = jobs.some(job => ['queued', 'training'].includes(job.status));

    if (!hasActiveJobs) return;

    const intervalId = setInterval(() => {
      setRefreshing(true);
      loadJobs();
    }, 15000); // Refresh every 15 seconds

    return () => clearInterval(intervalId);
  }, [jobs]);

  const loadJobs = async () => {
    try {
      const data = await api.getJobs();

      // Detect status changes and create notifications
      if (previousJobsRef.current.size > 0) {
        data.forEach((job: Job) => {
          const previousJob = previousJobsRef.current.get(job.id);
          if (previousJob && previousJob.status !== job.status) {
            // Status changed!
            const statusMessages: Record<string, { type: any; title: string; message: string }> = {
              'completed': {
                type: 'success' as const,
                title: 'Training Completed',
                message: `Job "${job.name}" has completed successfully!`,
              },
              'failed': {
                type: 'error' as const,
                title: 'Training Failed',
                message: `Job "${job.name}" has failed. Check logs for details.`,
              },
              'training': {
                type: 'info' as const,
                title: 'Training Started',
                message: `Job "${job.name}" is now training.`,
              },
            };

            const notification = statusMessages[job.status];
            if (notification) {
              addNotification(
                notification.type,
                notification.title,
                notification.message,
                {
                  jobId: job.id,
                  metadata: {
                    oldStatus: previousJob.status,
                    newStatus: job.status,
                    cost: job.cost_so_far,
                  }
                }
              );
            }
          }
        });
      }

      // Update previous jobs map
      const newJobsMap = new Map(data.map((job: Job) => [job.id, job]));
      previousJobsRef.current = newJobsMap;

      setJobs(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'active') return ['queued', 'training'].includes(job.status);
    if (filter === 'succeeded') return job.status === 'completed';
    if (filter === 'failed') return job.status === 'failed';
    return true;
  });

  return (
    <div className="h-screen flex flex-col">
      <TopBar user={{ name: 'User', role: 'ML Engineer' }} budget={budget} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeJobs={jobs.filter(j => j.status === 'training')}
          budget={budget}
          sessions={sessions}
          currentSessionId={currentSession?.session_id || null}
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900 mb-2">Training Jobs</h1>
                <p className="text-gray-600">Manage and monitor your ML training jobs</p>
              </div>

              {/* Status Indicators */}
              <div className="flex items-center gap-4">
                {/* Last Updated */}
                {lastUpdated && (
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Clock className="w-4 h-4" />
                    <span>Updated {Math.floor((Date.now() - lastUpdated.getTime()) / 1000)}s ago</span>
                  </div>
                )}

                {/* Refreshing Indicator */}
                {refreshing && (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-lg">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    >
                      <RefreshCw className="w-4 h-4 text-blue-600" />
                    </motion.div>
                    <span className="text-sm font-medium text-blue-700">Updating...</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-2 mb-6">
            {['all', 'active', 'succeeded', 'failed'].map((f) => (
              <button
                key={f}
                onClick={() => {
                  setFilter(f as any);
                  // Trigger sync to fetch latest job updates
                  setRefreshing(true);
                  loadJobs();
                }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  filter === f
                    ? 'bg-blue-500 text-white'
                    : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          {/* Jobs Grid */}
          {loading ? (
            <div>Loading...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {filteredJobs.map((job) => (
                <JobCard key={job.id} job={job} onUpdate={loadJobs} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function JobCard({ job, onUpdate }: { job: Job; onUpdate: () => void }) {
  const handleCancel = async () => {
    try {
      await api.cancelJob(job.id);
      onUpdate();
    } catch (error) {
      console.error('Failed to cancel job:', error);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow"
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{job.name}</h3>
          <p className="text-sm text-gray-500">{job.id}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
          job.status === 'completed' ? 'bg-green-100 text-green-700' :
          job.status === 'training' ? 'bg-blue-100 text-blue-700' :
          job.status === 'failed' ? 'bg-red-100 text-red-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {job.status}
        </span>
      </div>

      {job.status === 'training' && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-600">Progress</span>
            <span className="font-semibold">{job.progress}%</span>
          </div>
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="space-y-3">
        {/* Job details */}
        <div className="text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500">Model:</span>
            <span className="font-medium">{job.config.base_model}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Dataset:</span>
            <span className="font-medium">{job.config.dataset}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Optimization:</span>
            <span className="font-medium">{job.config.optimization}</span>
          </div>
          {job.metrics && (
            <>
              <div className="border-t pt-2 mt-2"></div>
              {job.metrics.f1_score && (
                <div className="flex justify-between">
                  <span className="text-gray-500">F1 Score:</span>
                  <span className="font-semibold text-green-600">{job.metrics.f1_score.toFixed(3)}</span>
                </div>
              )}
              {job.metrics.loss && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Loss:</span>
                  <span className="font-medium">{job.metrics.loss.toFixed(3)}</span>
                </div>
              )}
              {job.metrics.accuracy && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Precision:</span>
                  <span className="font-medium">{job.metrics.accuracy.toFixed(3)}</span>
                </div>
              )}
            </>
          )}
          <div className="border-t pt-2 mt-2"></div>
          <div className="flex justify-between">
            <span className="text-gray-500">Cost:</span>
            <span className="font-semibold text-blue-600">${job.cost_so_far.toFixed(2)}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.location.href = job.session_id ? `/chat?session=${job.session_id}` : `/chat`}
            className="flex-1 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors text-sm font-medium"
            disabled={!job.session_id}
            title={job.session_id ? 'View conversation that created this job' : 'No session available'}
          >
            View in Chat
          </button>
          {job.status === 'training' && (
            <button
              onClick={handleCancel}
              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Cancel job"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}