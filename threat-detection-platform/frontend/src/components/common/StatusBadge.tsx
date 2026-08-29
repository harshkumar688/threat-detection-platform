import clsx from 'clsx';

interface Props {
  status: string;
  size?: 'sm' | 'md';
}

const colorMap: Record<string, string> = {
  OPEN: 'bg-red-500/20 text-red-400',
  ACKNOWLEDGED: 'bg-yellow-500/20 text-yellow-400',
  RESOLVED: 'bg-green-500/20 text-green-400',
  FALSE_POSITIVE: 'bg-gray-500/20 text-gray-400',
  online: 'bg-green-500/20 text-green-400',
  offline: 'bg-gray-500/20 text-gray-400',
  processing: 'bg-blue-500/20 text-blue-400',
  error: 'bg-red-500/20 text-red-400',
};

export default function StatusBadge({ status, size = 'sm' }: Props) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium',
        colorMap[status] || 'bg-gray-500/20 text-gray-400',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      )}
    >
      {status.replace('_', ' ')}
    </span>
  );
}
