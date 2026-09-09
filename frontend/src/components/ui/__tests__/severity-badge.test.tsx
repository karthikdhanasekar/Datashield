import React from 'react'
import { render, screen } from '@testing-library/react'
import { SeverityBadge } from '../severity-badge'

describe('SeverityBadge', () => {
  it('renders the severity text', () => {
    render(<SeverityBadge severity="critical" />)
    expect(screen.getByText('critical')).toBeInTheDocument()
  })

  it('renders all four severity levels', () => {
    const { rerender } = render(<SeverityBadge severity="critical" />)
    expect(screen.getByText('critical')).toBeInTheDocument()

    rerender(<SeverityBadge severity="high" />)
    expect(screen.getByText('high')).toBeInTheDocument()

    rerender(<SeverityBadge severity="medium" />)
    expect(screen.getByText('medium')).toBeInTheDocument()

    rerender(<SeverityBadge severity="low" />)
    expect(screen.getByText('low')).toBeInTheDocument()
  })

  it('applies critical colour class', () => {
    render(<SeverityBadge severity="critical" />)
    const badge = screen.getByText('critical')
    expect(badge.className).toMatch(/red/)
  })

  it('applies high colour class', () => {
    render(<SeverityBadge severity="high" />)
    expect(screen.getByText('high').className).toMatch(/orange/)
  })

  it('applies medium colour class', () => {
    render(<SeverityBadge severity="medium" />)
    expect(screen.getByText('medium').className).toMatch(/yellow/)
  })

  it('applies low colour class', () => {
    render(<SeverityBadge severity="low" />)
    expect(screen.getByText('low').className).toMatch(/green/)
  })

  it('applies fallback style for unknown severity', () => {
    render(<SeverityBadge severity="unknown" />)
    const badge = screen.getByText('unknown')
    expect(badge.className).toMatch(/gray/)
  })

  it('applies small size class', () => {
    render(<SeverityBadge severity="high" size="sm" />)
    expect(screen.getByText('high').className).toMatch(/text-\[10px\]/)
  })

  it('applies custom className', () => {
    render(<SeverityBadge severity="low" className="my-custom-class" />)
    expect(screen.getByText('low').className).toMatch(/my-custom-class/)
  })
})
