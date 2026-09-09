import {
  cn,
  formatDate,
  formatDateTime,
  formatNumber,
  severityClass,
  riskLabel,
  riskColor,
  truncate,
  getDomain,
  MODULE_LABELS,
} from '../utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('a', 'b')).toBe('a b')
  })

  it('handles conditional classes', () => {
    expect(cn('a', false && 'b', 'c')).toBe('a c')
  })

  it('deduplicates tailwind classes', () => {
    // tailwind-merge removes duplicate/conflicting classes
    expect(cn('text-red-400', 'text-blue-400')).toBe('text-blue-400')
  })
})

describe('formatDate', () => {
  it('returns em dash for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('returns em dash for undefined', () => {
    expect(formatDate(undefined)).toBe('—')
  })

  it('formats a valid date string', () => {
    const result = formatDate('2024-01-15T00:00:00Z')
    expect(result).toMatch(/Jan/)
    expect(result).toMatch(/2024/)
  })

  it('accepts a Date object', () => {
    const result = formatDate(new Date('2024-06-01'))
    expect(result).toMatch(/Jun/)
  })
})

describe('formatNumber', () => {
  it('formats large numbers with commas', () => {
    expect(formatNumber(1000000)).toBe('1,000,000')
  })

  it('returns single-digit numbers as-is', () => {
    expect(formatNumber(5)).toBe('5')
  })
})

describe('severityClass', () => {
  it('returns critical class', () => {
    expect(severityClass('critical')).toBe('badge-critical')
  })
  it('returns high class', () => {
    expect(severityClass('high')).toBe('badge-high')
  })
  it('returns medium class', () => {
    expect(severityClass('medium')).toBe('badge-medium')
  })
  it('returns low class', () => {
    expect(severityClass('low')).toBe('badge-low')
  })
  it('returns fallback for unknown', () => {
    expect(severityClass('unknown')).toMatch(/gray/)
  })
})

describe('riskLabel', () => {
  it('returns Critical for score ≥ 80', () => {
    expect(riskLabel(80)).toBe('Critical')
    expect(riskLabel(100)).toBe('Critical')
  })
  it('returns High for score 50–79', () => {
    expect(riskLabel(50)).toBe('High')
    expect(riskLabel(79)).toBe('High')
  })
  it('returns Medium for score 25–49', () => {
    expect(riskLabel(25)).toBe('Medium')
    expect(riskLabel(49)).toBe('Medium')
  })
  it('returns Low for score 5–24', () => {
    expect(riskLabel(5)).toBe('Low')
    expect(riskLabel(24)).toBe('Low')
  })
  it('returns Safe for score < 5', () => {
    expect(riskLabel(0)).toBe('Safe')
    expect(riskLabel(4)).toBe('Safe')
  })
})

describe('riskColor', () => {
  it('returns red for critical scores', () => {
    expect(riskColor(85)).toBe('text-red-400')
  })
  it('returns orange for high scores', () => {
    expect(riskColor(60)).toBe('text-orange-400')
  })
  it('returns yellow for medium scores', () => {
    expect(riskColor(30)).toBe('text-yellow-400')
  })
  it('returns green for low and safe scores', () => {
    expect(riskColor(10)).toBe('text-green-400')
    expect(riskColor(0)).toBe('text-green-400')
  })
})

describe('truncate', () => {
  it('returns empty string for falsy input', () => {
    expect(truncate('')).toBe('')
  })
  it('does not truncate short strings', () => {
    expect(truncate('hello', 60)).toBe('hello')
  })
  it('truncates long strings with ellipsis', () => {
    const long = 'a'.repeat(70)
    const result = truncate(long, 60)
    expect(result).toHaveLength(61) // 60 + ellipsis char
    expect(result).toMatch(/…$/)
  })
})

describe('getDomain', () => {
  it('extracts domain from https URL', () => {
    expect(getDomain('https://www.github.com/user')).toBe('github.com')
  })
  it('strips www prefix', () => {
    expect(getDomain('https://www.linkedin.com/in/user')).toBe('linkedin.com')
  })
  it('returns the input for invalid URLs', () => {
    expect(getDomain('not-a-url')).toBe('not-a-url')
  })
})

describe('MODULE_LABELS', () => {
  it('has labels for core modules', () => {
    expect(MODULE_LABELS.breach).toBeDefined()
    expect(MODULE_LABELS.holehe).toBeDefined()
    expect(MODULE_LABELS.maigret).toBeDefined()
    expect(MODULE_LABELS.social_media).toBeDefined()
  })
})
