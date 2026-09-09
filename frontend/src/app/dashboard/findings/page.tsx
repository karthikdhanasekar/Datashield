'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scanApi, takedownApi } from '@/lib/api'
import {
  AlertTriangle, ExternalLink, Shield, FileText, Eye,
  Filter, RefreshCw, Loader2, CheckCircle, XCircle, Download
} from 'lucide-react'
import toast from 'react-hot-toast'

const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 }

export default function FindingsPage() {
  const [filter, setFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [exporting, setExporting] = useState(false)
  const qc = useQueryClient()

  const handleExport = async (fmt: 'csv' | 'json') => {
    setExporting(true)
    try {
      const res = await scanApi.exportFindings({ fmt })
      const blob   = new Blob([res.data], { type: fmt === 'csv' ? 'text/csv' : 'application/json' })
      const url    = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href     = url
      anchor.download = `datashield_findings.${fmt}`
      anchor.click()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${fmt.toUpperCase()}`)
    } catch {
      toast.error('No findings to export')
    } finally {
      setExporting(false)
    }
  }

  const { data: scans, isLoading } = useQuery({
    queryKey: ['scans', 'completed'],
    queryFn: async () => {
      const res = await scanApi.list({ status: 'completed', page_size: 5 })
      return res.data
    },
  })

  const latestScan = scans?.items?.[0]

  const { data: scanResult, isLoading: resultLoading } = useQuery({
    queryKey: ['scan-result', latestScan?.id],
    queryFn: async () => {
      if (!latestScan?.id) return null
      const res = await scanApi.get(latestScan.id)
      return res.data
    },
    enabled: !!latestScan?.id,
  })

  const markFalseMutation = useMutation({
    mutationFn: ({ id, isFalse }: { id: string; isFalse: boolean }) =>
      scanApi.updateFinding(id, { is_false_positive: isFalse }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scan-result'] })
      toast.success('Finding updated')
    },
  })

  const requestTakedownMutation = useMutation({
    mutationFn: (findingId: string) =>
      takedownApi.create({
        finding_id: findingId,
        template_type: 'gdpr_removal',
      }),
    onSuccess: () => {
      toast.success('Takedown request sent!')
      qc.invalidateQueries({ queryKey: ['takedowns'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to send takedown')
    },
  })

  const findings = scanResult?.findings || []
  const filtered = findings
    .filter((f: any) => filter === 'all' || f.severity === filter)
    .filter((f: any) => typeFilter === 'all' || f.finding_type === typeFilter)
    .filter((f: any) => !f.is_false_positive)
    .sort((a: any, b: any) => (severityOrder[a.severity as keyof typeof severityOrder] || 4) - (severityOrder[b.severity as keyof typeof severityOrder] || 4))

  if (isLoading) {
    return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
  }

  if (!latestScan) {
    return (
      <div className="text-center py-20">
        <Eye className="w-12 h-12 mx-auto mb-4 text-gray-600" />
        <h2 className="text-xl font-bold text-white mb-2">No findings yet</h2>
        <p className="text-gray-400 mb-6">Run your first scan to discover exposed personal information.</p>
        <a href="/dashboard/scan" className="bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-6 py-3 rounded-lg transition-colors inline-flex items-center gap-2">
          Start First Scan
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Findings</h1>
          <p className="text-gray-400 text-sm">
            {findings.length} exposures found in latest {latestScan?.scan_type} scan
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Export buttons */}
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 disabled:opacity-40 transition-colors"
          >
            {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            disabled={exporting}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 disabled:opacity-40 transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            JSON
          </button>
          <a
            href="/dashboard/scan"
            className="flex items-center gap-2 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-400 px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            New Scan
          </a>
        </div>
      </div>

      {/* Summary cards */}
      {scanResult && (
        <div className="grid grid-cols-4 gap-4">
          {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
            <button
              key={sev}
              onClick={() => setFilter(filter === sev ? 'all' : sev)}
              className={`glass-card p-4 text-center transition-all ${filter === sev ? 'border-cyan-500/50' : 'hover:border-white/20'}`}
            >
              <div className={`text-2xl font-black badge-${sev} rounded-lg p-1`}>
                {scanResult.scan[`${sev}_count`]}
              </div>
              <div className="text-xs text-gray-400 mt-1 capitalize">{sev}</div>
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Filter className="w-4 h-4 text-gray-500" />
        {['all', 'breach', 'social_media', 'search_engine', 'document', 'paste_site'].map((type) => (
          <button
            key={type}
            onClick={() => setTypeFilter(type)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              typeFilter === type
                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                : 'border-white/10 text-gray-400 hover:border-white/20 hover:text-white'
            }`}
          >
            {type.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Findings list */}
      {resultLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-500" />
          <p>No findings match your current filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((finding: any) => (
            <div key={finding.id} className="glass-card p-5 hover:border-white/20 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <span className={`badge-${finding.severity} text-xs font-bold px-2 py-1 rounded flex-shrink-0 mt-0.5`}>
                    {finding.severity.toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-white font-medium text-sm">{finding.source_domain || 'Unknown source'}</span>
                      <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded">
                        {finding.finding_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {finding.source_title && (
                      <p className="text-gray-400 text-xs mb-1 truncate">{finding.source_title}</p>
                    )}
                    {finding.description && (
                      <p className="text-gray-300 text-sm leading-relaxed">{finding.description}</p>
                    )}
                    {/* Risk factors */}
                    <div className="flex flex-wrap gap-2 mt-2">
                      {finding.credential_exposure && <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded">Credential Exposure</span>}
                      {finding.identity_theft_risk && <span className="text-xs text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded">Identity Theft Risk</span>}
                      {finding.financial_risk && <span className="text-xs text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded">Financial Risk</span>}
                      {finding.government_id_exposure && <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded">Gov ID Exposed</span>}
                    </div>
                    {/* Exposed data types */}
                    {finding.exposed_data_types?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {finding.exposed_data_types.map((dt: string) => (
                          <span key={dt} className="text-xs text-gray-400 bg-white/5 px-1.5 py-0.5 rounded">
                            {dt.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-2 flex-shrink-0">
                  {finding.source_url && (
                    <a
                      href={finding.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-gray-400 hover:text-cyan-400 bg-white/5 rounded-lg transition-colors"
                      title="View source"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  <button
                    onClick={() => requestTakedownMutation.mutate(finding.id)}
                    disabled={requestTakedownMutation.isPending || finding.is_removed}
                    className="p-2 text-gray-400 hover:text-orange-400 bg-white/5 hover:bg-orange-500/10 rounded-lg transition-colors disabled:opacity-40"
                    title="Request removal"
                  >
                    <Shield className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => markFalseMutation.mutate({ id: finding.id, isFalse: !finding.is_false_positive })}
                    className="p-2 text-gray-400 hover:text-gray-200 bg-white/5 rounded-lg transition-colors"
                    title="Mark as false positive"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {finding.snippet && (
                <div className="mt-3 p-3 bg-white/5 rounded-lg text-xs text-gray-400 border border-white/5 line-clamp-2">
                  {finding.snippet}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
