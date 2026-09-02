import { cn } from '../lib/utils';

interface ModelOutputProps {
  prompt?: string;
  response: string;
  model?: string | null;
  provider?: string | null;
  label?: string;
  className?: string;
}

export default function ModelOutput({ prompt, response, model, provider, label = 'MODEL OUTPUT', className }: ModelOutputProps) {
  return (
    <div className={cn('relative', className)}>
      {/* Stage Label */}
      <div className="flex items-center gap-2 mb-2 pl-12">
        <span className="text-[10px] font-mono text-cp-text-muted opacity-50">02</span>
        <span className="cp-section-title">{label}</span>
      </div>
      
      {/* Content */}
      <div className="cp-panel border-l-2 border-l-cp-border ml-4">
        {prompt && (
          <div className="mb-3 pb-3 border-b border-cp-border/50">
            <span className="cp-label block mb-1.5">USER PROMPT</span>
            <div className="p-3 bg-cp-surface rounded-md text-body-sm text-cp-text">
              {prompt}
            </div>
          </div>
        )}
        
        <div>
          <span className="cp-label block mb-1.5">RAW RESPONSE</span>
          <div className="p-3 bg-cp-surface rounded-md text-body-sm text-cp-text whitespace-pre-wrap font-mono leading-relaxed">
            {response}
          </div>
        </div>
        
        {(model || provider) && (
          <div className="mt-3 pt-3 cp-divider flex items-center gap-4">
            {model && (
              <span className="text-caption font-mono text-cp-text-muted">{model}</span>
            )}
            {provider && (
              <span className="text-caption text-cp-text-muted">·</span>
            )}
            {provider && (
              <span className="text-caption text-cp-text-muted">{provider}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
