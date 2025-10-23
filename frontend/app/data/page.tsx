'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { FolderOpen, Upload, Download, Trash2, Database } from 'lucide-react';
import { api } from '@/lib/api';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';
import { formatBytes, formatRelativeTime } from '@/lib/utils';
import { ConfirmDialog } from '@/components/dialogs/ConfirmDialog';

interface Dataset {
  id: string;
  name: string;
  version: string;
  size_bytes: number;
  rows: number;
  columns: number;
  format: string;
  created_at: string;
  created_by: string;
  description?: string;
}

export default function DataPage() {
  // Session management
  const { currentSession, sessions } = useSession(true);

  // Get session budget (not global budget)
  const { sessionBudget } = useBudget(currentSession?.session_id);

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{ isOpen: boolean; dataset: Dataset | null }>({
    isOpen: false,
    dataset: null,
  });

  // Budget display - fallback to defaults if not loaded
  const budget = sessionBudget || { spent: 0, limit: 50, remaining: 50 };

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    try {
      const data = await api.getDatasets();
      setDatasets(data);
    } catch (error) {
      console.error('Failed to load datasets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await api.uploadDataset(file);
      await loadDatasets();
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteClick = (dataset: Dataset) => {
    setDeleteDialog({ isOpen: true, dataset });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.dataset) return;

    try {
      // TODO: Implement delete API call
      console.log('Deleting dataset:', deleteDialog.dataset.id);
      // await api.deleteDataset(deleteDialog.dataset.id);
      // await loadDatasets();
      setDeleteDialog({ isOpen: false, dataset: null });
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <TopBar user={{ name: 'User', role: 'ML Engineer' }} budget={budget} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeJobs={[]}
          budget={budget}
          sessions={sessions}
          currentSessionId={currentSession?.session_id || null}
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Datasets</h1>
              <p className="text-gray-600">Manage your training data with DVC versioning</p>
            </div>
            
            <label className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium cursor-pointer transition-colors flex items-center gap-2">
              <Upload className="w-5 h-5" />
              {uploading ? 'Uploading...' : 'Upload Dataset'}
              <input
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                disabled={uploading}
                accept=".csv,.json,.xlsx,.parquet"
              />
            </label>
          </div>

          {/* Datasets Table */}
          {loading ? (
            <div>Loading...</div>
          ) : datasets.length === 0 ? (
            <EmptyState onUpload={() => (document.querySelector('input[type="file"]') as HTMLInputElement | null)?.click()} />
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Version</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Size</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Rows</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Format</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Created</th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {datasets.map((dataset) => (
                    <DatasetRow key={dataset.id} dataset={dataset} onDelete={handleDeleteClick} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteDialog.isOpen}
        title="Delete Dataset"
        message={`Are you sure you want to delete "${deleteDialog.dataset?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteDialog({ isOpen: false, dataset: null })}
      />
    </div>
  );
}

function DatasetRow({ dataset, onDelete }: { dataset: Dataset; onDelete: (dataset: Dataset) => void }) {
  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="hover:bg-gray-50 transition-colors"
    >
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
            <Database className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">{dataset.name}</p>
            {dataset.description && (
              <p className="text-xs text-gray-500">{dataset.description}</p>
            )}
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm font-mono text-gray-600">{dataset.version}</span>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm text-gray-900">{formatBytes(dataset.size_bytes)}</span>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm text-gray-900">{dataset.rows.toLocaleString()}</span>
      </td>
      <td className="px-6 py-4">
        <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded">
          {dataset.format.toUpperCase()}
        </span>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm text-gray-500">{formatRelativeTime(dataset.created_at)}</span>
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center justify-end gap-2">
          <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors" title="Download dataset">
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(dataset)}
            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="Delete dataset"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </td>
    </motion.tr>
  );
}

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="text-center py-12">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <FolderOpen className="w-8 h-8 text-gray-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">No datasets yet</h3>
      <p className="text-gray-600 mb-6">Upload your first dataset to get started</p>
      <button
        onClick={onUpload}
        className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
      >
        Upload Dataset
      </button>
    </div>
  );
}