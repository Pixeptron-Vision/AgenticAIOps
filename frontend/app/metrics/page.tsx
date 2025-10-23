'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, TrendingUp, Activity, Zap } from 'lucide-react';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { useSession } from '@/hooks/useSession';
import { useBudget } from '@/hooks/useBudget';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api } from '@/lib/api';

export default function MetricsPage() {
  // Session management
  const { currentSession, sessions } = useSession(true);

  // Get session budget (not global budget)
  const { sessionBudget } = useBudget(currentSession?.session_id);

  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('7d');

  // Budget display - fallback to defaults if not loaded
  const budget = sessionBudget || { spent: 0, limit: 50, remaining: 50 };

  // Mock data - replace with real API calls
  const trainingData = [
    { date: 'Mon', jobs: 4, cost: 12.5 },
    { date: 'Tue', jobs: 6, cost: 18.2 },
    { date: 'Wed', jobs: 3, cost: 9.1 },
    { date: 'Thu', jobs: 8, cost: 24.3 },
    { date: 'Fri', jobs: 5, cost: 15.7 },
    { date: 'Sat', jobs: 2, cost: 6.8 },
    { date: 'Sun', jobs: 3, cost: 10.2 },
  ];

  const accuracyData = [
    { model: 'DistilBERT', accuracy: 88.3 },
    { model: 'TinyBERT', accuracy: 83.1 },
    { model: 'RoBERTa', accuracy: 91.2 },
    { model: 'MobileNet', accuracy: 86.7 },
  ];

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
        
        <div className="flex-1 overflow-y-auto p-8 bg-gray-50">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Analytics Dashboard</h1>
              <p className="text-gray-600">Monitor training performance and resource usage</p>
            </div>
            
            <div className="flex gap-2">
              {['24h', '7d', '30d'].map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range as any)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    timeRange === range
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatsCard
              icon={Activity}
              label="Total Jobs"
              value="31"
              change="+12%"
              positive
            />
            <StatsCard
              icon={TrendingUp}
              label="Avg Accuracy"
              value="87.3%"
              change="+2.1%"
              positive
            />
            <StatsCard
              icon={Zap}
              label="Avg Training Time"
              value="18 min"
              change="-15%"
              positive
            />
            <StatsCard
              icon={BarChart3}
              label="Total Cost"
              value="$96.50"
              change="+8%"
              positive={false}
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Training Activity */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Training Activity</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trainingData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="jobs" stroke="#3b82f6" strokeWidth={2} name="Jobs Completed" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Cost Breakdown */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Cost Breakdown</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={trainingData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  <Bar dataKey="cost" fill="#8b5cf6" name="Cost ($)" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Model Performance */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Model Accuracy Comparison</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={accuracyData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" stroke="#6b7280" />
                  <YAxis type="category" dataKey="model" stroke="#6b7280" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar dataKey="accuracy" fill="#10b981" name="Accuracy (%)" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
              <div className="space-y-4">
                {[
                  { action: 'Model deployed', model: 'sentiment-v1', time: '5 min ago' },
                  { action: 'Training completed', model: 'defect-det-v2', time: '23 min ago' },
                  { action: 'Dataset uploaded', model: 'reviews-v3', time: '1 hour ago' },
                  { action: 'Training started', model: 'ner-model-v1', time: '2 hours ago' },
                ].map((item, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">{item.action}</p>
                      <p className="text-xs text-gray-500">{item.model}</p>
                    </div>
                    <span className="text-xs text-gray-400">{item.time}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatsCard({ icon: Icon, label, value, change, positive }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl border border-gray-200 p-6"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center">
          <Icon className="w-6 h-6 text-blue-600" />
        </div>
        <span className={`text-sm font-semibold ${positive ? 'text-green-600' : 'text-red-600'}`}>
          {change}
        </span>
      </div>
      <p className="text-2xl font-bold text-gray-900 mb-1">{value}</p>
      <p className="text-sm text-gray-600">{label}</p>
    </motion.div>
  );
}