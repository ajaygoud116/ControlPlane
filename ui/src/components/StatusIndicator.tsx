import { cn } from '../lib/utils';

type StatusType = 'allow' | 'modify' | 'verify' | 'escalate' | 'block' | 'unknown' | 'checking';

interface StatusIndicatorProps {
  status: StatusType;
  label?: string;
  showDot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const STATUS_CONFIG: Record<StatusType, { dotClass: string; textClass: string }> = {
  allow: { dotClass: 'status-dot-allow', textClass: 'text-cp-allow' },
  modify: { dotClass: 'status-dot-modify', textClass: 'text-cp-modify' },
  verify: { dotClass: 'status-dot-verify', textClass: 'text-cp-verify' },
  escalate: { dotClass: 'status-dot-escalate', textClass: 'text-cp-escalate' },
  block: { dotClass: 'status-dot-block', textClass: 'text-cp-block' },
  unknown: { dotClass: 'status-dot-unknown', textClass: 'text-cp-unknown' },
  checking: { dotClass: 'bg-cp-unknown animate-pulse-dot', textClass: 'text-cp-text-muted' },
};

export default function StatusIndicator({ 
  status, 
  label, 
  showDot = true, 
  size = 'sm',
  className 
}: StatusIndicatorProps) {
  const config = STATUS_CONFIG[status];
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2';
  
  return (
    <div className={cn('inline-flex items-center gap-1.5', className)}>
      {showDot && (
        <div className={cn('rounded-full', dotSize, config.dotClass)} />
      )}
      <span className={cn('font-medium', size === 'sm' ? 'text-caption' : 'text-body-sm', config.textClass)}>
        {label || status.toUpperCase()}
      </span>
    </div>
  );
}
