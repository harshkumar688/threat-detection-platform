import { ReactNode } from 'react';
import clsx from 'clsx';

interface Props {
  title: string;
  value: string | number;
  icon: ReactNode;
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'gray';
  subtitle?: string;
}

const colorMap = {
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  green: 'bg-green-500/10 text-green-400 border-green-500/30',
  yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  red: 'bg-red-500/10 text-red-400 border-red-500/30',
  gray: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
};

export default function StatCard({ title, value, icon, color = 'blue', subtitle }: Props) {
  return (
    <div className={clsx('rounded-xl border p-5', colorMap[color])}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className="opacity-60">{icon}</div>
      </div>
    </div>
  );
}
