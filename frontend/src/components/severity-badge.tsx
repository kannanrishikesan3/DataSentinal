import { cn } from '@/lib/utils'
import type { Severity } from '@/types/api'

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: 'bg-severity-critical-bg text-severity-critical-fg',
  high: 'bg-severity-high-bg text-severity-high-fg',
  medium: 'bg-severity-medium-bg text-severity-medium-fg',
  low: 'bg-severity-low-bg text-severity-low-fg',
  informational: 'bg-severity-info-bg text-severity-info-fg',
}

const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-severity-critical',
  high: 'bg-severity-high',
  medium: 'bg-severity-medium',
  low: 'bg-severity-low',
  informational: 'bg-severity-info',
}

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  informational: 'Informational',
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
        SEVERITY_STYLES[severity],
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', SEVERITY_DOT[severity])} />
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

// `var(--...)` references, not resolved hex — SVG presentation attributes
// (Recharts' fill/stroke props) accept CSS custom properties directly, so
// these stay live across a system light/dark switch instead of freezing
// at whatever scheme was active on first render, and always match the
// badges/dots above from one source of truth (index.css).
export const SEVERITY_CHART_COLORS: Record<Severity, string> = {
  critical: 'var(--severity-critical)',
  high: 'var(--severity-high)',
  medium: 'var(--severity-medium)',
  low: 'var(--severity-low)',
  informational: 'var(--severity-info)',
}

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'informational']
