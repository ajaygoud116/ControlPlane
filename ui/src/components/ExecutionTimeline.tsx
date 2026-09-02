import { cn } from '../lib/utils';

interface TimelineStep {
  id: string;
  label: string;
  status: 'complete' | 'active' | 'pending' | 'error';
  content?: React.ReactNode;
}

interface ExecutionTimelineProps {
  steps: TimelineStep[];
  className?: string;
}

export default function ExecutionTimeline({ steps, className }: ExecutionTimelineProps) {
  return (
    <div className={cn('space-y-0', className)}>
      {steps.map((step, index) => (
        <div key={step.id} className="relative">
          {/* Connector line */}
          {index > 0 && (
            <div className={cn(
              'absolute left-4 top-0 w-px h-4 -mt-4',
              step.status === 'complete' || step.status === 'active' 
                ? 'bg-cp-brand' 
                : 'bg-cp-border'
            )} />
          )}
          
          {/* Step content */}
          <div className={cn(
            'flex gap-4 pb-4',
            step.status === 'pending' && 'opacity-50'
          )}>
            {/* Step indicator */}
            <div className={cn(
              'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-body-sm font-medium',
              step.status === 'complete' && 'bg-cp-brand text-white',
              step.status === 'active' && 'bg-cp-brand text-white animate-pulse-soft',
              step.status === 'pending' && 'bg-cp-surface-2 text-cp-text-muted border border-cp-border',
              step.status === 'error' && 'bg-cp-block text-white'
            )}>
              {step.status === 'complete' ? '✓' : 
               step.status === 'active' ? '●' :
               step.status === 'error' ? '✕' : (index + 1)}
            </div>
            
            {/* Step content */}
            <div className="flex-1 min-w-0 pt-1">
              <div className="text-body-sm font-medium text-cp-text">{step.label}</div>
              {step.content && (
                <div className="mt-2">{step.content}</div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
