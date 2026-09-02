import { cn, formatTimestamp } from '../lib/utils';

interface AuditEvent {
  timestamp: string;
  event_type: string;
  details?: string;
}

interface AuditTimelineProps {
  events: AuditEvent[];
  className?: string;
}

const EVENT_LABELS: Record<string, string> = {
  MODEL_OUTPUT: 'Model Output Received',
  PERFORMANCE_FINDING: 'Performance Analysis Complete',
  COST_FINDING: 'Cost Analysis Complete',
  RESPONSIBILITY_FINDING: 'Responsibility Analysis Complete',
  POLICY_EVALUATED: 'Policy Evaluated',
  DECISION_ALLOW: 'Decision: Allow',
  DECISION_MODIFY: 'Decision: Modify',
  DECISION_BLOCK: 'Decision: Block',
  DECISION_ESCALATE: 'Decision: Escalate',
  DECISION_VERIFY: 'Decision: Verify',
  INTERVENTION_APPLIED: 'Intervention Applied',
  RESPONSE_RELEASED: 'Response Released',
};

export default function AuditTimeline({ events, className }: AuditTimelineProps) {
  return (
    <div className={cn('cp-panel', className)}>
      <div className="cp-section-title mb-4">AUDIT TRACE</div>
      
      <div className="relative">
        {/* Timeline Rail */}
        <div className="absolute left-3 top-0 bottom-0 w-px bg-cp-border" />
        
        <div className="space-y-0">
          {events.map((event, index) => (
            <div key={index} className="relative">
              {/* Event Node */}
              <div className="flex items-start gap-3 pb-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-cp-surface-2 border border-cp-border flex items-center justify-center z-10">
                  <div className="w-1.5 h-1.5 rounded-full bg-cp-text-muted" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-caption font-mono text-cp-text-muted">
                      {formatTimestamp(event.timestamp)}
                    </span>
                    <span className="text-body-sm font-medium text-cp-text">
                      {EVENT_LABELS[event.event_type] || event.event_type}
                    </span>
                  </div>
                  {event.details && (
                    <p className="text-caption text-cp-text-secondary mt-0.5">{event.details}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
