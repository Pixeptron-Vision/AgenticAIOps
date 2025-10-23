// components/sidebar/BudgetDisplay.tsx
import { DollarSign, TrendingDown } from 'lucide-react';
import { Progress } from '@/components/ui/Progress';

interface BudgetDisplayProps {
  spent?: number;
  limit?: number;
  savings?: number;
}

export function BudgetDisplay({ spent = 0, limit = 50, savings = 0 }: BudgetDisplayProps) {
  const percentUsed = (spent / limit) * 100;

  return (
    <div className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 border-t border-green-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-green-600" />
          <span className="text-sm font-semibold text-gray-800">Session Budget</span>
        </div>
        <span className="text-xs text-gray-500">{percentUsed.toFixed(1)}% used</span>
      </div>

      <Progress value={percentUsed} className="h-2 mb-2" />

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-600">
          ${spent.toFixed(2)} / ${limit.toFixed(2)}
        </span>
        <span className="text-green-600 font-semibold">
          ${(limit - spent).toFixed(2)} left
        </span>
      </div>

      {savings > 0 && (
        <div className="flex items-center gap-1 mt-2 p-2 bg-white/60 rounded-lg">
          <TrendingDown className="w-3 h-3 text-green-600" />
          <span className="text-xs text-green-700 font-medium">
            Saved ${savings.toFixed(2)} with optimizations
          </span>
        </div>
      )}
    </div>
  );
}