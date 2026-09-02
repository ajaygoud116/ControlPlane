import { cn } from '../lib/utils';

interface PolicyCardProps {
  policy: {
    policy_id: string;
    name: string;
    version: string;
    description?: string;
    scope?: string;
    assurance_requirements?: Record<string, string>;
    hard_constraints?: {
      blocked_patterns?: string[];
      required_verifications?: string[];
      escalation_triggers?: string[];
    };
  };
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

export default function PolicyCard({ policy, selected, onClick, className }: PolicyCardProps) {
  return (
    <div
      className={cn(
        'cp-panel cursor-pointer transition-all duration-200',
        selected 
          ? 'border-cp-brand bg-cp-brand-light/30 shadow-sm' 
          : 'hover:border-cp-border-strong hover:shadow-card-hover',
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h4 className="text-heading-sm text-cp-text">{policy.name}</h4>
          <p className="text-caption font-mono text-cp-text-muted mt-0.5">v{policy.version}</p>
        </div>
        {selected && (
          <div className="w-5 h-5 rounded-full bg-cp-brand flex items-center justify-center">
            <span className="text-white text-caption">✓</span>
          </div>
        )}
      </div>
      
      {policy.description && (
        <p className="text-body-sm text-cp-text-secondary mb-3">{policy.description}</p>
      )}
      
      {policy.assurance_requirements && (
        <div className="space-y-1.5">
          {Object.entries(policy.assurance_requirements).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-caption">
              <span className="text-cp-text-secondary capitalize">{key}</span>
              <span className="font-mono text-cp-text">{value}</span>
            </div>
          ))}
        </div>
      )}
      
      {policy.hard_constraints && (
        <div className="mt-3 pt-3 cp-divider">
          <div className="flex flex-wrap gap-1.5">
            {policy.hard_constraints.blocked_patterns?.map((pattern, i) => (
              <span key={i} className="cp-badge-block text-caption">{pattern}</span>
            ))}
            {policy.hard_constraints.escalation_triggers?.map((trigger, i) => (
              <span key={i} className="cp-badge-escalate text-caption">{trigger}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
