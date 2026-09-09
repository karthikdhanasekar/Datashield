'use client'

import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scanApi } from '@/lib/api'
import {
  SearchCheck, Download, Loader2, ExternalLink,
  AlertTriangle, Filter, X, FileJson, FileText,
} from 'lucide-react'
import toast from 'react-hot-toast'

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const
const FINDING_TYPES = [
  'breach', 'social_media', 'search_engine', 'document',
  'dark_web_indicator', 'paste_site', 'forum', 'news',
] as const

type Severity = typeof SEVERITIES[number]

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'text-red-400 bg-red-500/10 border-red-500/30',
  high:     'text-orange-400 bg-orange-500/10 border-orange-500/30',
  medium:   'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  low:      'text-blue-400 bg-blue-500/10 border-blue-500/30',
}

export default function SearchPage() {
  const [query, setQuery]               = useState('')
  const [debouncedQ, setDebouncedQ]     = useState('')
  const [severity, setSeverity]         = useState<string>('')
  const [findingType, setFindingType]   = useState<string>('')
  const [page, setPage]                 = useState(1)
  const [exporting, setExporting]       = useState(false)

  // Debounce: only fire query after user stops typing 400ms
  const handleInput = useCallback((val: string) => {
    setQuery(val)
    setPage(1)
    const t = setTimeout(() => setDebouncedQ(val), 400)
    return () => clearTimeout(t)
  }, [])

  const searchEnabled = debouncedQ.trim().length >= 2

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['findings-search', debouncedQ, severity, findingType, page],
    queryFn: async () => {
      const res = await scanApi.search({
        q: debouncedQ,
        ...(severity     ? { severity }     : {}),
        ...(findingType  ? { finding_type: findingType } : {}),
        page,
        page_size: 20,
      })
      return res.data
    },
    enabled: searchEnabled,
    staleTime: 30_000,
    placeholderData: (prev: any) => prev,
  })

  const hits       = data?.hits ?? []
  const total      = data?.total ?? 0
  const source     = data?.source ?? ''
  const totalPages = Math.ceil(total / 20)

  const handleExport = async (fmt: 'csv' | 'json') => {
    if (!debouncedQ) return
    setExporting(true)
    try {
      const res = await scanApi.exportFindings({
        fmt,
        ...(severity ? { severity } : {}),
      })
      const blob   = new Blob([res.data], { type: fmt === 'csv' ? 'text/csv' : 'application/json' })
      const url    = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href  = url
      anchor.download = `datashield_findings.${fmt}`
      anchor.click()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${fmt.toUpperCase()} successfully`)
    } catch {
      toast.error('Export failed — no findings match current filters')
    } finally {
      setExporting(false)
    }
  }

  const clearFilters = () => {
    setSeverity('')
    setFindingType('')
    setPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <SearchCheck className="w-6 h-6 text-cyan-400" />
            Search Findings
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Full-text search across all your discovered exposures
          </p>
        </div>

        {/* Export buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting || !searchEnabled}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm
              bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Export CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            disabled={exporting || !searchEnabled}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm
              bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileJson className="w-4 h-4" />}
            Export JSON
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="relative">
        <SearchCheck className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          placeholder="Search descriptions, domains, snippets… (min 2 chars)"
          className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-xl
            text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50
            focus:ring-1 focus:ring-cyan-500/30 transition-colors text-sm"
          aria-label="Search findings"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setDebouncedQ(''); setPage(1) }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <Filter className="w-4 h-4 text-gray-500 flex-shrink-0" />

        {/* Severity filter */}
        <div className="flex gap-1.5 flex-wrap">
          {SEVERITIES.map((s) => (
            <button
              key={s}
              onClick={() => { setSeverity(severity === s ? '' : s); setPage(1) }}
              className={`text-xs px-3 py-1.5 rounded-full border capitalize transition-colors ${
                severity === s
                  ? SEVERITY_COLORS[s]
                  : 'border-white/10 text-gray-400 hover:border-white/20 hover:text-white'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <span className="text-gray-600 text-sm hidden sm:block">|</span>

        {/* Type filter */}
        <select
          value={findingType}
          onChange={(e) => { setFindingType(e.target.value); setPage(1) }}
          className="text-xs bg-white/5 border border-white/10 text-gray-400 rounded-lg px-3 py-1.5
            focus:outline-none focus:border-cyan-500/50 transition-colors"
          aria-label="Filter by finding type"
        >
          <option value="">All types</option>
          {FINDING_TYPES.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>

        {(severity || findingType) && (
          <button
            onClick={clearFilters}
            className="text-xs text-gray-500 hover:text-white flex items-center gap-1 transition-colors"
          >
            <X className="w-3 h-3" /> Clear filters
          </button>
        )}
      </div>

      {/* Results */}
      {!searchEnabled ? (
        <div className="text-center py-20 text-gray-600">
          <SearchCheck className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg">Enter at least 2 characters to search</p>
          <p className="text-sm mt-1 opacity-60">
            Searches descriptions, domains, source titles, and snippets
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>
      ) : hits.length === 0 ? (
        <div className="text-center py-20 text-gray-600">
          <AlertTriangle className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No findings match <span className="text-gray-400">"{debouncedQ}"</span></p>
          {(severity || findingType) && (
            <button onClick={clearFilters} className="mt-3 text-cyan-400 text-sm hover:underline">
              Clear filters and try again
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Result count + source badge */}
          <div className="flex items-center justify-between text-sm text-gray-400">
            <span>
              {isFetching && <Loader2 className="w-3 h-3 animate-spin inline mr-1" />}
              {total.toLocaleString()} result{total !== 1 ? 's' : ''} for{' '}
              <span className="text-white">"{debouncedQ}"</span>
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${
              source === 'elasticsearch'
                ? 'border-cyan-500/30 text-cyan-400 bg-cyan-500/10'
                : 'border-white/10 text-gray-500'
            }`}>
              {source === 'elasticsearch' ? '⚡ Elasticsearch' : '🐘 PostgreSQL'}
            </span>
          </div>

          {/* Hit cards */}
          <div className="space-y-3">
            {hits.map((hit: any) => {
              const sev = hit.severity as Severity
              const colorClass = SEVERITY_COLORS[sev] ?? 'text-gray-400 bg-white/5 border-white/10'

              // Build highlighted snippet
              const highlights = hit.highlights ?? {}
              const highlightText: string =
                highlights.description?.[0] ??
                highlights.snippet?.[0] ??
                hit.snippet ??
                hit.description ??
                ''

              return (
                <article
                  key={hit.id}
                  className="glass-card p-5 hover:border-white/20 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <span className={`text-xs font-bold px-2 py-1 rounded border flex-shrink-0 mt-0.5 uppercase ${colorClass}`}>
                        {sev}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-white font-medium text-sm">
                            {hit.source_domain ?? 'Unknown source'}
                          </span>
                          <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded">
                            {(hit.finding_type ?? '').replace(/_/g, ' ')}
                          </span>
                          {hit.risk_score != null && (
                            <span className="text-xs text-gray-500">
                              risk {Number(hit.risk_score).toFixed(1)}
                            </span>
                          )}
                        </div>

                        {hit.source_title && (
                          <p className="text-gray-400 text-xs mb-1 truncate">{hit.source_title}</p>
                        )}

                        {highlightText && (
                          <p
                            className="text-gray-300 text-sm leading-relaxed line-clamp-3"
                            dangerouslySetInnerHTML={{
                              // Sanitise: only allow <em> for highlight markers
                              __html: highlightText
                                .replace(/</g, '&lt;')
                                .replace(/&lt;em>/g, '<em class="text-cyan-300 not-italic font-medium">')
                                .replace(/&lt;\/em>/g, '</em>'),
                            }}
                          />
                        )}

                        {/* Exposed data types */}
                        {Array.isArray(hit.exposed_data_types) && hit.exposed_data_types.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {hit.exposed_data_types.map((dt: string) => (
                              <span key={dt} className="text-xs text-gray-500 bg-white/5 px-1.5 py-0.5 rounded">
                                {dt.replace(/_/g, ' ')}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Source link */}
                    {hit.source_url && (
                      <a
                        href={hit.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 text-gray-400 hover:text-cyan-400 bg-white/5 rounded-lg transition-colors flex-shrink-0"
                        aria-label={`Open ${hit.source_domain}`}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 rounded-lg text-sm bg-white/5 border border-white/10
                  text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="text-gray-500 text-sm px-3">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 rounded-lg text-sm bg-white/5 border border-white/10
                  text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
