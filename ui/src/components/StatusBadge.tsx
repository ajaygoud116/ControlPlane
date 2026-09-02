import { cn } from '../lib/utils'

type Color = 'allow' | 'modify' | 'block' | 'escalate' | 'verify' | 'brand' | 'accent' | 'gray'

const colorMap: Record<Color, string> = {
  allow: 'bg-cp-allow-soft text-cp-allow border-cp-allow/20',
  modify: 'bg-cp-modify-soft text-cp-modify border-cp-modify/20',
  block: 'bg-cp-block-soft text-cp-block border-cp-block/20',
  escalate: 'bg-cp-escalate-soft text-cp-escalate border-cp-escalate/20',
  verify: 'bg-cp-verify-soft text-cp-verify border-cp-verify/20',
  brand: 'bg-cp-brand-light text-cp-brand border-cp-brand/20',
  accent: 'bg-cp-accent-light text-cp-accent border-cp-accent/20',
  gray: 'bg-cp-surface-2 text-cp-text-muted border-cp-border',
}

interface StatusBadgeProps {
  label: string
  color?: Color
  dot?: boolean
  size?: 'sm' | 'md'
  className?: string
}

export default function StatusBadge({ label, color = 'gray', dot = false, size = 'sm', className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 border rounded font-mono font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs',
        colorMap[color],
        className
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full', colorMap[color].split(' ')[0])} />}
      {label}
    </span>
  )
}
