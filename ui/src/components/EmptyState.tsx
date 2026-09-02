import { cn } from '../lib/utils';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export default function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 px-8 text-center', className)}>
      {icon && (
        <div className="w-12 h-12 rounded-full bg-cp-surface-2 border border-cp-border flex items-center justify-center mb-4">
          <span className="text-body-lg text-cp-text-muted">{icon}</span>
        </div>
      )}
      <h3 className="text-heading-lg text-cp-text mb-2">{title}</h3>
      <p className="text-body text-cp-text-secondary max-w-md mb-6 leading-relaxed">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="cp-btn-primary"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
