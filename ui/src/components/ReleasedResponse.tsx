import { cn } from '../lib/utils';

interface ReleasedResponseProps {
  response: string;
  intervention?: string;
  rawResponse?: string;
  className?: string;
}

export default function ReleasedResponse({ response, intervention, rawResponse, className }: ReleasedResponseProps) {
  const hasTransformation = intervention && rawResponse && rawResponse !== response;
  
  return (
    <div className={cn('relative', className)}>
      {/* Stage Label */}
      <div className="flex items-center gap-2 mb-2 pl-12">
        <span className="text-[10px] font-mono text-cp-text-muted opacity-50">07</span>
        <span className="cp-section-title text-cp-brand">GOVERNED OUTPUT</span>
      </div>
      
      {/* Content */}
      <div className="cp-panel border-2 border-cp-brand/20 bg-cp-brand-light/10 ml-4">
        {hasTransformation && (
          <div className="mb-3 pb-3 border-b border-cp-brand/10">
            <div className="flex items-center gap-2 mb-2">
              <span className="cp-label">RAW</span>
              <span className="text-caption text-cp-text-muted">→</span>
              <span className="cp-label text-cp-brand">GOVERNED</span>
            </div>
            <div className="p-3 bg-cp-surface rounded-md text-body-sm text-cp-text-secondary line-through opacity-60">
              {rawResponse}
            </div>
          </div>
        )}
        
        <div>
          <span className="cp-label block mb-1.5 text-cp-brand">RELEASED RESPONSE</span>
          <div className="p-4 bg-cp-surface rounded-md text-body text-cp-text whitespace-pre-wrap leading-relaxed">
            {response}
          </div>
        </div>
        
        {intervention && (
          <div className="mt-3 pt-3 cp-divider">
            <div className="flex items-center gap-2">
              <span className="cp-label">Intervention:</span>
              <span className="text-body-sm text-cp-modify font-medium">{intervention}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
