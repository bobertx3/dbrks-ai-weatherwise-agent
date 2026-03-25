import { cn } from '@/lib/utils';
import {
  TruckIcon,
  AlertTriangleIcon,
  CheckCircle2Icon,
  TagIcon,
} from 'lucide-react';

interface StatusCardsProps {
  counts: Record<string, number>;
}

const statusConfig = [
  {
    key: 'In-Transit',
    label: 'In-Transit',
    icon: TruckIcon,
    color: 'text-blue-400',
    border: 'border-blue-500/30',
    bg: 'bg-blue-500/10',
  },
  {
    key: 'Delayed',
    label: 'Delayed',
    icon: AlertTriangleIcon,
    color: 'text-red-400',
    border: 'border-red-500/30',
    bg: 'bg-red-500/10',
  },
  {
    key: 'Delivered',
    label: 'Delivered',
    icon: CheckCircle2Icon,
    color: 'text-green-400',
    border: 'border-green-500/30',
    bg: 'bg-green-500/10',
  },
  {
    key: 'Label-Create',
    label: 'Label Created',
    icon: TagIcon,
    color: 'text-zinc-400',
    border: 'border-zinc-500/30',
    bg: 'bg-zinc-500/10',
  },
];

export function StatusCards({ counts }: StatusCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {statusConfig.map(({ key, label, icon: Icon, color, border, bg }) => (
        <div
          key={key}
          className={cn('rounded-lg border p-4', border, bg)}
        >
          <div className="flex items-center gap-2 mb-2">
            <Icon className={cn('h-4 w-4', color)} />
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {label}
            </span>
          </div>
          <div className={cn('text-3xl font-bold', color)}>
            {counts[key] ?? 0}
          </div>
        </div>
      ))}
    </div>
  );
}
