import { cn } from '../lib/utils';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export default function PageHeader({ eyebrow, title, description, action, className }: PageHeaderProps) {
  return (
    <div className={cn('mb-6', className)}>
      {eyebrow && (
        <div className="cp-eyebrow mb-2">{eyebrow}</div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-display-sm text-cp-text">{title}</h1>
          {description && (
            <p className="text-body text-cp-text-secondary mt-1.5 max-w-2xl">{description}</p>
          )}
        </div>
        {action && <div className="flex-shrink-0">{action}</div>}
      </div>
    </div>
  );
}
