import { cn } from '../lib/utils';

interface DemoBadgeProps {
  className?: string;
}

export default function DemoBadge({ className }: DemoBadgeProps) {
  return (
    <div className={cn(
      'inline-flex items-center gap-2 px-3 py-1.5 rounded-md',
      'bg-cp-accent-light/30 border border-cp-accent/10',
      className
    )}>
      <div className="w-1.5 h-1.5 rounded-full bg-cp-accent animate-pulse-dot" />
      <span className="text-[10px] font-medium text-cp-accent-dim tracking-wider">DEMO ENVIRONMENT</span>
    </div>
  );
}
