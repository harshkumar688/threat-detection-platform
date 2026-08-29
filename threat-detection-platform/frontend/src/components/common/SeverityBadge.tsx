import clsx from 'clsx';
import { Severity } from '../../types/common';

interface Props {
  level: Severity | string;
  size?: 'sm' | 'md';
}

const colorMap: Record<string, string> = {
  LOW: 'bg-green-500/20 text-green-400 border-green-500/40',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
  CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/40',
};

export default function SeverityBadge({ level, size = 'sm' }: Props) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border font-medium uppercase',
        colorMap[level] || colorMap.MEDIUM,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      )}
    >
      {level}
    </span>
  );
}
