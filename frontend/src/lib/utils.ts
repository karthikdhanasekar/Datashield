/**
 * DataShield OSINT - Utility Functions
 */
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind classes (shadcn/ui utility) */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a date string to readable form */
export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

/** Format date with time */
export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return '—'
  return new Date(date).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** Format a number with commas */
export function formatNumber(n: number): string {
  return n.toLocaleString('en-US')
}

/** Get severity badge CSS class */
export function severityClass(severity: string): string {
  const map: Record<string, string> = {
    critical: 'badge-critical',
    high:     'badge-high',
    medium:   'badge-medium',
    low:      'badge-low',
  }
  return map[severity] ?? 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
}

/** Get risk level label from exposure score */
export function riskLabel(score: number): string {
  if (score >= 80) return 'Critical'
  if (score >= 50) return 'High'
  if (score >= 25) return 'Medium'
  if (score >= 5)  return 'Low'
  return 'Safe'
}

/** Get risk level text color class */
export function riskColor(score: number): string {
  if (score >= 80) return 'text-red-400'
  if (score >= 50) return 'text-orange-400'
  if (score >= 25) return 'text-yellow-400'
  if (score >= 5)  return 'text-green-400'
  return 'text-green-400'
}

/** Truncate long strings */
export function truncate(str: string, maxLen = 60): string {
  if (!str) return ''
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str
}

/** Extract domain from URL */
export function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

/** Convert module key to display label */
export const MODULE_LABELS: Record<string, string> = {
  breach:        'HIBP Breach Check',
  holehe:        'Holehe (120+ sites)',
  maigret:       'Maigret (3000+ sites)',
  social_media:  'Social Media',
  search_engine: 'Search Engine',
  document:      'Document Scanner',
  paste:         'Paste Sites',
  phone:         'Phone OSINT',
  shodan:        'Shodan Infrastructure',
}
