// components/sidebar/ActiveJobsList.tsx
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, MessageSquare } from 'lucide-react';
import { Progress } from '@/components/ui/Progress';
import { Job } from '@/types/jobs';
import Link from 'next/link';

interface ActiveJobsListProps {
  jobs: Job[];
}

export function ActiveJobsList({ jobs }: ActiveJobsListProps) {
  if (jobs.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-gray-400">No active jobs</p>
      </div>
    );
  }

  return (
    <AnimatePresence>
      {jobs.map((job) => (
        <motion.div
          key={job.id}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          className="mb-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors cursor-pointer"
        >
          {/* Job Header */}
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="flex items-center gap-2">
                {job.status === 'training' ? (
                  <Settings className="w-4 h-4 text-blue-500 animate-spin-slow" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-purple-500" />
                )}
                <h4 className="text-sm font-semibold text-gray-800 truncate">
                  {job.name}
                </h4>
              </div>
              <p className="text-xs text-gray-500 mt-0.5 truncate">
                {job.id}
              </p>
            </div>
          </div>

          {/* Progress */}
          {job.status === 'training' && (
            <div className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-600">Progress</span>
                <span className="text-xs font-semibold text-gray-800">
                  {job.progress}%
                </span>
              </div>
              <Progress value={job.progress} className="h-1.5" />
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">ETA: {job.eta} min</span>
            <span className="text-gray-700 font-medium">
              ${job.cost_so_far.toFixed(2)}
            </span>
          </div>

          {/* Action */}
          <div className="mt-2 pt-2 border-t border-gray-100">
            <Link
              href={`/jobs/${job.id}`}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              View Details →
            </Link>
          </div>
        </motion.div>
      ))}
    </AnimatePresence>
  );
}