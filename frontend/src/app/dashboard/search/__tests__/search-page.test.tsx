/**
 * SearchPage unit tests
 *
 * We mock the API client so no real HTTP calls are made.
 * We mock next/navigation so the component can render without a Next.js router.
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ── Mocks ──────────────────────────────────────────────────────────────────

jest.mock('next/navigation', () => ({
  useRouter:   () => ({ push: jest.fn() }),
  usePathname: () => '/dashboard/search',
  useParams:   () => ({}),
}))

jest.mock('@/lib/api', () => ({
  scanApi: {
    search: jest.fn().mockResolvedValue({
      data: {
        hits:      [],
        total:     0,
        page:      1,
        page_size: 20,
        source:    'postgresql',
      },
    }),
    exportFindings: jest.fn().mockResolvedValue({ data: 'col1,col2\nval1,val2' }),
  },
}))

// ── Helpers ────────────────────────────────────────────────────────────────

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('SearchPage', () => {
  beforeEach(() => jest.clearAllMocks())

  it('renders the search input', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    expect(
      screen.getByPlaceholderText(/search descriptions/i)
    ).toBeInTheDocument()
  })

  it('shows prompt when query is too short', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/enter at least 2 characters/i)).toBeInTheDocument()
  })

  it('renders severity filter buttons', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /critical/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /high/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /medium/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /low/i })).toBeInTheDocument()
  })

  it('renders type filter dropdown', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('combobox', { name: /filter by finding type/i })).toBeInTheDocument()
  })

  it('shows export buttons', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /export json/i })).toBeInTheDocument()
  })

  it('export buttons are disabled when no query', async () => {
    const SearchPage = (await import('../page')).default
    render(<SearchPage />, { wrapper: makeWrapper() })
    const csvBtn = screen.getByRole('button', { name: /export csv/i })
    expect(csvBtn).toBeDisabled()
  })
})
