import { cn, decisionLabel, decisionBadgeClass } from '../lib/utils';

interface ComparisonRow {
  label: string;
  balanced: string;
  strict: string;
  type?: 'finding' | 'policy' | 'action' | 'release';
}

interface ComparisonTableProps {
  title: string;
  rows: ComparisonRow[];
  className?: string;
}

export default function ComparisonTable({ title, rows, className }: ComparisonTableProps) {
  return (
    <div className={cn('cp-panel', className)}>
      <div className="cp-section-title mb-4">{title}</div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-body-sm">
          <thead>
            <tr className="border-b border-cp-border">
              <th className="text-left py-2 pr-4 font-medium text-cp-text-secondary"></th>
              <th className="text-left py-2 px-4 font-medium text-cp-text-secondary">BALANCED</th>
              <th className="text-left py-2 pl-4 font-medium text-cp-text-secondary">STRICT</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-b border-cp-border/50 last:border-0">
                <td className="py-3 pr-4 text-caption font-medium text-cp-text-muted uppercase tracking-wider">
                  {row.label}
                </td>
                <td className="py-3 px-4">
                  {row.type === 'finding' && (
                    <span className={cn(
                      'inline-flex items-center gap-1.5',
                      row.balanced.includes('⚠') ? 'text-cp-escalate' : 'text-cp-allow'
                    )}>
                      {row.balanced}
                    </span>
                  )}
                  {row.type === 'policy' && (
                    <span className="text-body-sm font-medium text-cp-text">{row.balanced}</span>
                  )}
                  {row.type === 'action' && (
                    <span className="text-body-sm text-cp-text">{row.balanced}</span>
                  )}
                  {row.type === 'release' && (
                    <span className={cn(
                      'inline-flex items-center gap-1.5',
                      row.balanced === '✓' ? 'text-cp-allow' : 'text-cp-block'
                    )}>
                      {row.balanced === '✓' ? '✓ Released' : '✕ Blocked'}
                    </span>
                  )}
                  {!row.type && (
                    <span className="text-body-sm text-cp-text">{row.balanced}</span>
                  )}
                </td>
                <td className="py-3 pl-4">
                  {row.type === 'finding' && (
                    <span className={cn(
                      'inline-flex items-center gap-1.5',
                      row.strict.includes('⚠') ? 'text-cp-escalate' : 'text-cp-allow'
                    )}>
                      {row.strict}
                    </span>
                  )}
                  {row.type === 'policy' && (
                    <span className="text-body-sm font-medium text-cp-text">{row.strict}</span>
                  )}
                  {row.type === 'action' && (
                    <span className="text-body-sm text-cp-text">{row.strict}</span>
                  )}
                  {row.type === 'release' && (
                    <span className={cn(
                      'inline-flex items-center gap-1.5',
                      row.strict === '✓' ? 'text-cp-allow' : 'text-cp-block'
                    )}>
                      {row.strict === '✓' ? '✓ Released' : '✕ Blocked'}
                    </span>
                  )}
                  {!row.type && (
                    <span className="text-body-sm text-cp-text">{row.strict}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
