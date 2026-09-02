import { cn, stateLabel, stateSeverity, severityBg, severityText, dimensionLabel } from '../lib/utils';

interface FindingCardProps {
  finding: {
    finding_id: string;
    dimension: string;
    finding_type: string;
    state: string;
    explanation?: string | null;
    evidence?: {
      claim_text?: string | null;
    };
  };
  className?: string;
}

export default function FindingCard({ finding, className }: FindingCardProps) {
  const severity = stateSeverity(finding.state);
  const label = stateLabel(finding.state);
  const bgClass = severityBg(severity);
  const textClass = severityText(severity);
  
  return (
    <div className={cn(
      'cp-panel',
      bgClass,
      className
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="cp-section-title">{dimensionLabel(finding.dimension)}</span>
            <span className={cn('text-caption font-medium', textClass)}>
              {label}
            </span>
          </div>
          
          {finding.explanation && (
            <p className="text-body-sm text-cp-text">{finding.explanation}</p>
          )}
          
          {finding.evidence?.claim_text && (
            <p className="text-caption text-cp-text-secondary mt-1 italic">
              "{finding.evidence.claim_text}"
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
