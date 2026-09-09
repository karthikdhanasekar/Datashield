/**
 * SeverityBadge — reusable severity pill component
 */
import { cn } from '@/lib/utils'

interface SeverityBadgeProps {
  severity: 'critical' | 'high' | 'medium' | 'low' | string
  className?: string
  size?: 'sm' | 'md'
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low:      'bg-green-500/20 text-green-400 border-green-500/30',
}

export function SeverityBadge({ severity, className, size = 'md' }: SeverityBadgeProps) {
  const styles = SEVERITY_STYLES[severity?.toLowerCase()] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30'
  return (
    <span className={cn(
      'inline-flex items-center font-bold uppercase tracking-wide border rounded',
      size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5',
      styles,
      className,
    )}>
      {severity}
    </span>
  )
}
