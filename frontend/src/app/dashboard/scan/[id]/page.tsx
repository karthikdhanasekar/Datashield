'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { scanApi } from '@/lib/api'
import {
  Loader2, Shield, CheckCircle, XCircle, AlertTriangle,
  ExternalLink, RefreshCw, ChevronRight, Eye, Zap, Radio
} from 'lucide-react'
import Link from 'next/link'

const MODULE_LABELS: Record<string, string> = {
  breach:          '🔓 Breach Detection (XposedOrNot)',
  holehe:          '📧 Holehe (120+ sites)',
  maigret:         '🕵️ Maigret (3000+ sites)',
  sherlock:        '🔍 Sherlock (400+ sites)',
  social_analyzer: '📊 Social-Analyzer (300+ sites)',
  social_media:    '👤 Social Media Scan',
  search_engine:   '🔍 Search Engine Dorks',
  document:        '📄 Document Scanner',
  paste:           '📋 Paste Sites',
  phone:           '📱 Phone OSINT',
  shodan:          '🌐 Shodan Infrastructure',
  linkedin:        '💼 LinkedIn',
  instagram:       '📸 Instagram',
  darkweb:         '🕳️ Dark Web Indicators',
  spiderfoot:      '🕷️ SpiderFoot Modules',
}

const SEV_COLORS: Record<string, string> = {
  critical: 'text-red-400 bg-red-500/20 border-red-500/30',
  high:     'text-orange-400 bg-orange-500/20 border-orange-500/30',
  medium:   'text-yellow-400 bg-yellow-500/20 border-yellow-500/30',
  low:      'text-green-400 bg-green-500/20 border-green-500/30',
}

export default function ScanStatusPage() {
  const params        = useParams()
  const router        = useRouter()
  const qc            = useQueryClient()
  const scanId        = params.id as string
  const wsRef         = useRef<WebSocket | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [liveFeed,    setLiveFeed]    = useState<any[]>([])

  // ── HTTP polling (fallback / initial load) ────────────────────────────────
  const { data, isLoading, error } = useQuery({
    queryKey: ['scan', scanId],
    queryFn:  async () => {
      const res = await scanApi.get(scanId)
      return res.data
    },
    // Only poll when WS is not connected AND scan is still active
    refetchInterval: (query) => {
      if (wsConnected) return false
      const status = query.state.data?.scan?.status
      return (status === 'running' || status === 'pending') ? 2000 : false
    },
    staleTime: 0,
  })

  const scan     = data?.scan
  const findings = data?.findings || []
  const isActive = scan?.status === 'running' || scan?.status === 'pending'

  // ── WebSocket — real-time progress ───────────────────────────────────────
  useEffect(() => {
    if (!scanId || !isActive) return

    const token = localStorage.getItem('access_token')
    if (!token) return

    const wsBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      .replace('https://', 'wss://')
      .replace('http://', 'ws://')
    const wsUrl  = `${wsBase}/ws/scan/${scanId}?token=${encodeURIComponent(token)}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'progress' || msg.type === 'complete' || msg.type === 'error') {
            // Refresh React Query cache with latest scan data
            qc.invalidateQueries({ queryKey: ['scan', scanId] })
          }
          if (msg.type === 'finding') {
            setLiveFeed((prev) => [msg.data, ...prev].slice(0, 20))
          }
          if (msg.type === 'complete' || msg.type === 'error') {
            ws.close(1000)
            setWsConnected(false)
          }
        } catch {}
      }

      ws.onclose = () => setWsConnected(false)
      ws.onerror = () => {
        setWsConnected(false)
        ws.close()
      }
    } catch {
      setWsConnected(false)
    }

    return () => {
      wsRef.current?.close(1000)
      wsRef.current = null
    }
  }, [scanId, isActive, qc])

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-cyan-400" />
        <p className="text-gray-400">Loading scan...</p>
      </div>
    )
  }

  if (error || !scan) {
    return (
      <div className="text-center py-24">
        <XCircle className="w-10 h-10 mx-auto mb-4 text-red-400" />
        <p className="text-gray-400">Scan not found.</p>
        <Link href="/dashboard/scan" className="text-cyan-400 mt-2 inline-block">← New Scan</Link>
      </div>
    )
  }

  // Merge live feed with loaded findings (live first, dedup by id)
  const allFindings = [
    ...liveFeed,
    ...findings.filter((f: any) => !liveFeed.some((l) => l.id === f.id)),
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <Link href="/dashboard" className="hover:text-white">Dashboard</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="capitalize">{scan.scan_type} Scan</span>
          </div>
          <h1 className="text-2xl font-bold text-white capitalize">
            {scan.scan_type} Scan
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {/* Connection indicator */}
          {isActive && (
            <div className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
              wsConnected
                ? 'border-green-500/30 bg-green-500/10 text-green-400'
                : 'border-gray-500/30 bg-white/5 text-gray-500'
            }`}>
              {wsConnected ? <Zap className="w-3 h-3" /> : <Radio className="w-3 h-3" />}
              {wsConnected ? 'Live' : 'Polling'}
            </div>
          )}
          {!isActive && (
            <Link
              href="/dashboard/findings"
              className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              <Eye className="w-4 h-4" />
              View All Findings
            </Link>
          )}
        </div>
      </div>

      {/* Status Card */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {isActive ? (
              <div className="w-10 h-10 bg-cyan-500/20 rounded-xl flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
              </div>
            ) : scan.status === 'completed' ? (
              <div className="w-10 h-10 bg-green-500/20 rounded-xl flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
            ) : (
              <div className="w-10 h-10 bg-red-500/20 rounded-xl flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
            )}
            <div>
              <div className="text-white font-semibold capitalize">{scan.status}</div>
              <div className="text-xs text-gray-500">
                Started {scan.started_at ? new Date(scan.started_at).toLocaleTimeString() : '—'}
              </div>
            </div>
          </div>
          <div className="text-3xl font-black text-cyan-400">{scan.progress}%</div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-white/5 rounded-full h-3 overflow-hidden">
          <div
            className={`h-3 rounded-full transition-all duration-700 ${
              scan.status === 'completed' ? 'bg-green-500' :
              scan.status === 'failed'    ? 'bg-red-500'   : 'bg-cyan-500'
            }`}
            style={{ width: `${scan.progress}%` }}
          />
        </div>

        {/* Module status grid */}
        {scan.modules_run?.length > 0 && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-2">
            {scan.modules_run.map((mod: string) => {
              const done = scan.modules_completed?.includes(mod)
              return (
                <div
                  key={mod}
                  className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${
                    done
                      ? 'border-green-500/30 bg-green-500/10 text-green-400'
                      : isActive
                      ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400'
                      : 'border-white/10 bg-white/5 text-gray-500'
                  }`}
                >
                  {done
                    ? <CheckCircle className="w-3 h-3" />
                    : isActive
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <div className="w-3 h-3 rounded-full border border-current" />
                  }
                  <span className="truncate">{MODULE_LABELS[mod] || mod}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Completed summary */}
      {scan.status === 'completed' && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
              <div key={sev} className="glass-card p-4 text-center">
                <div className={`text-3xl font-black ${SEV_COLORS[sev].split(' ')[0]}`}>
                  {scan[`${sev}_count`]}
                </div>
                <div className="text-xs text-gray-400 mt-1 capitalize">{sev}</div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between p-4 glass-card">
            <div>
              <div className="text-gray-400 text-sm">Overall Exposure Score</div>
              <div className={`text-4xl font-black mt-1 ${
                scan.exposure_score >= 80 ? 'text-red-400' :
                scan.exposure_score >= 50 ? 'text-orange-400' :
                scan.exposure_score >= 25 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                {scan.exposure_score.toFixed(0)}<span className="text-lg text-gray-500">/100</span>
              </div>
            </div>
            <Link
              href="/dashboard/findings"
              className="bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-6 py-3 rounded-xl transition-colors flex items-center gap-2"
            >
              <Eye className="w-4 h-4" />
              Review {scan.total_findings} Findings
            </Link>
          </div>
        </>
      )}

      {/* Live findings feed */}
      {allFindings.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-400" />
            {isActive ? (
              <span className="flex items-center gap-2">
                Live Findings
                {wsConnected && (
                  <span className="inline-flex items-center gap-1 text-xs text-green-400">
                    <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                    real-time
                  </span>
                )}
              </span>
            ) : 'Top Findings'}
          </h2>
          <div className="space-y-3">
            {allFindings.slice(0, 8).map((f: any, i: number) => (
              <div
                key={f.id || i}
                className={`flex items-start gap-3 p-3 bg-white/5 rounded-lg transition-all ${
                  i === 0 && isActive && wsConnected ? 'animate-pulse-once border border-cyan-500/20' : ''
                }`}
              >
                <span className={`text-xs font-bold px-2 py-0.5 rounded border flex-shrink-0 mt-0.5 ${SEV_COLORS[f.severity] ?? ''}`}>
                  {(f.severity ?? '').toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white font-medium truncate">
                    {f.source_name || f.source_domain || 'Unknown source'}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 line-clamp-2">
                    {f.description}
                  </div>
                </div>
                {f.source_url && (
                  <a href={f.source_url} target="_blank" rel="noopener noreferrer"
                    className="text-gray-500 hover:text-cyan-400 flex-shrink-0">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            ))}
          </div>
          {allFindings.length > 8 && (
            <Link href="/dashboard/findings"
              className="mt-4 block text-center text-sm text-cyan-400 hover:text-cyan-300">
              View all {allFindings.length} findings →
            </Link>
          )}
        </div>
      )}

      {/* Error state */}
      {scan.status === 'failed' && scan.error_message && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
          <div className="flex items-center gap-2 text-red-400 mb-2">
            <XCircle className="w-5 h-5" />
            <span className="font-semibold">Scan Failed</span>
          </div>
          <p className="text-sm text-gray-400">{scan.error_message}</p>
          <Link href="/dashboard/scan"
            className="mt-3 inline-flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300">
            <RefreshCw className="w-3 h-3" /> Try again
          </Link>
        </div>
      )}
    </div>
  )
}