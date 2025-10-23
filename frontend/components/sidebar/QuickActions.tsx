// components/sidebar/QuickActions.tsx
import { FileText, Database, Rocket, Code } from 'lucide-react';

const actions = [
  { icon: FileText, label: 'Train Model', color: 'text-blue-500' },
  { icon: Database, label: 'Upload Data', color: 'text-green-500' },
  { icon: Rocket, label: 'Deploy Model', color: 'text-purple-500' },
  { icon: Code, label: 'Export ONNX', color: 'text-orange-500' },
];

export function QuickActions() {
  return (
    <div className="grid grid-cols-2 gap-2">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            className="flex flex-col items-center gap-2 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all"
          >
            <Icon className={`w-5 h-5 ${action.color}`} />
            <span className="text-xs font-medium text-gray-700 text-center">
              {action.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}