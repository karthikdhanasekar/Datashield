'use client'

import { useQuery } from '@tanstack/react-query'
import { scanApi, takedownApi, notificationApi } from '@/lib/api'
import {
  Shield, AlertTriangle, CheckCircle, Clock, Activity,
  TrendingUp, Eye, Bell, ArrowUpRight, Loader2, Search,
  Download, BarChart3
} from 'lucide-react'
import Link from 'next/link'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  BarChart, Bar, CartesianGrid, Legend
} from 'recharts'

const severityColors = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
}

/** Build a per-day findings trend from last N completed scans */
function buildTrendData(scans: any[]) {
  const completed = scans
    .filter((s: any) => s.status === 'completed' && s.completed_at)
    .slice(0, 20)
    .reverse()

  return completed.map((s: any) => ({
    date: new Date(s.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    critical: s.critical_count || 0,
    high:     s.high_count     || 0,
    medium:   s.medium_count   || 0,
    low:      s.low_count      || 0,
    total:    s.total_findings || 0,
    score:    Math.round(s.exposure_score || 0),
  }))
}

export default function DashboardPage() {
  const { data: score, isLoading: scoreLoading } = useQuery({
    queryKey: ['exposure-score'],
    queryFn: async () => {
      const res = await scanApi.getExposureScore()
      return res.data
    },
  })

  const { data: scans } = useQuery({
    queryKey: ['scans', 'history'],
    queryFn: async () => {
      const res = await scanApi.getHistory(20)
      return res.data
    },
  })

  const { data: takedowns } = useQuery({
    queryKey: ['takedowns'],
    queryFn: async () => {
      const res = await takedownApi.list({ page_size: 5 })
      return res.data
    },
  })

  const { data: notifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await notificationApi.list({ unread_only: true })
      return res.data
    },
  })

  const riskColorMap: Record<string, string> = {
    safe:     'text-green-400',
    low:      'text-green-400',
    medium:   'text-yellow-400',
    high:     'text-orange-400',
    critical: 'text-red-400',
  }
  const riskColor = riskColorMap[score?.risk_level || 'safe'] || 'text-gray-400'
  const trendData = buildTrendData(scans?.items || [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Privacy Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Monitor your digital exposure and protection status</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/search"
            className="flex items-center gap-2 border border-white/10 hover:border-cyan-500/40 text-gray-400 hover:text-cyan-400 px-3 py-2 rounded-lg text-sm transition-colors"
          >
            <Search className="w-4 h-4" />
            Search
          </Link>
          <Link
            href="/dashboard/scan"
            className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Shield className="w-4 h-4" />
            New Scan
          </Link>
        </div>
      </div>

      {/* Exposure Score Widget */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Exposure Score</h2>
          <span className={`text-sm font-bold px-3 py-1 rounded-full ${
            score?.risk_level === 'safe'     ? 'bg-green-500/20 text-green-400' :
            score?.risk_level === 'critical' ? 'bg-red-500/20 text-red-400'    :
            score?.risk_level === 'high'     ? 'bg-orange-500/20 text-orange-400' :
            'bg-yellow-500/20 text-yellow-400'
          }`}>
            {score?.risk_level?.toUpperCase() || 'SAFE'}
          </span>
        </div>

        {scoreLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Score gauge */}
            <div className="text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#1a3a73" strokeWidth="12" />
                  <circle
                    cx="80" cy="80" r="70"
                    fill="none"
                    stroke={score?.score >= 80 ? '#ef4444' : score?.score >= 50 ? '#f97316' : '#06b6d4'}
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${(score?.score || 0) / 100 * 440} 440`}
                    transform="rotate(-90 80 80)"
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute text-center">
                  <div className={`text-4xl font-black ${riskColor}`}>{score?.score || 0}</div>
                  <div className="text-xs text-gray-500">/100</div>
                </div>
              </div>
              <p className="text-gray-400 text-sm mt-2">
                {score?.score === 0 ? 'No exposures found' : 'Privacy risk score'}
              </p>
            </div>

            {/* Breakdown bars */}
            <div className="space-y-3">
              {Object.entries(score?.breakdown || {}).map(([severity, count]) => (
                <div key={severity} className="flex items-center gap-3">
                  <span className={`text-xs font-bold uppercase w-16 badge-${severity} px-2 py-0.5 rounded`}>
                    {severity}
                  </span>
                  <div className="flex-1 bg-white/5 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${Math.min((count as number) * 10, 100)}%`,
                        backgroundColor: severityColors[severity as keyof typeof severityColors],
                      }}
                    />
                  </div>
                  <span className="text-white font-bold text-sm w-6 text-right">{count as number}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: 'Active Leaks',
            value: (score?.breakdown?.critical || 0) + (score?.breakdown?.high || 0),
            icon: AlertTriangle,
            color: 'text-red-400',
            bg: 'bg-red-500/10',
          },
          {
            label: 'Removed',
            value: takedowns?.items?.filter((t: any) => t.status === 'removed').length || 0,
            icon: CheckCircle,
            color: 'text-green-400',
            bg: 'bg-green-500/10',
          },
          {
            label: 'Pending Requests',
            value: takedowns?.items?.filter((t: any) => ['pending', 'sent'].includes(t.status)).length || 0,
            icon: Clock,
            color: 'text-yellow-400',
            bg: 'bg-yellow-500/10',
          },
          {
            label: 'Unread Alerts',
            value: notifications?.length || 0,
            icon: Bell,
            color: 'text-cyan-400',
            bg: 'bg-cyan-500/10',
          },
        ].map((stat) => (
          <div key={stat.label} className="glass-card p-4">
            <div className={`w-10 h-10 ${stat.bg} rounded-xl flex items-center justify-center mb-3`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <div className={`text-2xl font-black ${stat.color}`}>{stat.value}</div>
            <div className="text-gray-400 text-sm mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* ── Scan History Analytics ──────────────────────────────────────────── */}
      {trendData.length > 1 && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              Scan History — Findings Trend
            </h2>
            <Link
              href="/dashboard/search?fmt=csv"
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-cyan-400 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export all
            </Link>
          </div>

          {/* Stacked bar chart: findings per scan by severity */}
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e3a6e" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{ background: '#0d1f4a', border: '1px solid #1e3a6e', borderRadius: 8 }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#9ca3af' }}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 11, color: '#9ca3af' }}
                />
                <Bar dataKey="critical" stackId="a" fill="#ef4444" name="Critical" radius={[0,0,0,0]} />
                <Bar dataKey="high"     stackId="a" fill="#f97316" name="High" />
                <Bar dataKey="medium"   stackId="a" fill="#eab308" name="Medium" />
                <Bar dataKey="low"      stackId="a" fill="#22c55e" name="Low" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Exposure score trend line */}
          {trendData.some(d => d.score > 0) && (
            <>
              <p className="text-xs text-gray-500 mt-4 mb-2">Exposure Score Over Time</p>
              <div className="h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData} margin={{ top: 2, right: 4, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#06b6d4" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" hide />
                    <YAxis domain={[0, 100]} hide />
                    <Tooltip
                      contentStyle={{ background: '#0d1f4a', border: '1px solid #1e3a6e', borderRadius: 8 }}
                      labelStyle={{ color: '#e5e7eb' }}
                      formatter={(v: number) => [`${v}/100`, 'Score']}
                    />
                    <Area
                      type="monotone"
                      dataKey="score"
                      stroke="#06b6d4"
                      strokeWidth={2}
                      fill="url(#scoreGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}

      {/* Recommendations */}
      {score?.recommendations && score.recommendations.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            Recommendations
          </h2>
          <ul className="space-y-2">
            {score.recommendations.map((rec: string, i: number) => (
              <li key={i} className="flex items-start gap-3 text-sm text-gray-300">
                <span className="text-cyan-400 mt-0.5">→</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recent Scans */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Scans</h2>
          <Link
            href="/dashboard/findings"
            className="text-cyan-400 text-sm hover:text-cyan-300 flex items-center gap-1"
          >
            View all <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        {scans?.items?.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No scans yet. Start your first scan to discover exposures.</p>
            <Link
              href="/dashboard/scan"
              className="text-cyan-400 text-sm mt-2 inline-block hover:text-cyan-300"
            >
              Start a scan →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scans?.items?.map((scan: any) => (
              <Link
                key={scan.id}
                href={`/dashboard/scan/${scan.id}`}
                className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Eye className="w-4 h-4 text-cyan-400" />
                  <div>
                    <div className="text-sm text-white font-medium capitalize">
                      {scan.scan_type} scan
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(scan.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {scan.total_findings > 0 && (
                    <div className="flex items-center gap-1.5 text-xs">
                      {scan.critical_count > 0 && (
                        <span className="text-red-400 font-bold">{scan.critical_count}C</span>
                      )}
                      {scan.high_count > 0 && (
                        <span className="text-orange-400 font-bold">{scan.high_count}H</span>
                      )}
                      <span className="text-gray-500">{scan.total_findings} total</span>
                    </div>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    scan.status === 'completed'
                      ? 'badge-low'
                      : scan.status === 'running'
                      ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                      : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                  }`}>
                    {scan.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const severityColors = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
}

export default function DashboardPage() {
  const { data: score, isLoading: scoreLoading } = useQuery({
    queryKey: ['exposure-score'],
    queryFn: async () => {
      const res = await scanApi.getExposureScore()
      return res.data
    },
  })

  const { data: scans } = useQuery({
    queryKey: ['scans'],
    queryFn: async () => {
      const res = await scanApi.list({ page_size: 5 })
      return res.data
    },
  })

  const { data: takedowns } = useQuery({
    queryKey: ['takedowns'],
    queryFn: async () => {
      const res = await takedownApi.list({ page_size: 5 })
      return res.data
    },
  })

  const { data: notifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await notificationApi.list({ unread_only: true })
      return res.data
    },
  })

  const riskColorMap: Record<string, string> = {
    safe:     'text-green-400',
    low:      'text-green-400',
    medium:   'text-yellow-400',
    high:     'text-orange-400',
    critical: 'text-red-400',
  }
  const riskColor = riskColorMap[score?.risk_level || 'safe'] || 'text-gray-400'

  const breakdownData = score?.breakdown
    ? Object.entries(score.breakdown).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Privacy Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Monitor your digital exposure and protection status</p>
        </div>
        <Link
          href="/dashboard/scan"
          className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
        >
          <Shield className="w-4 h-4" />
          New Scan
        </Link>
      </div>

      {/* Exposure Score Widget */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Exposure Score</h2>
          <span className={`text-sm font-bold px-3 py-1 rounded-full ${
            score?.risk_level === 'safe' ? 'bg-green-500/20 text-green-400' :
            score?.risk_level === 'critical' ? 'bg-red-500/20 text-red-400' :
            score?.risk_level === 'high' ? 'bg-orange-500/20 text-orange-400' :
            'bg-yellow-500/20 text-yellow-400'
          }`}>
            {score?.risk_level?.toUpperCase() || 'SAFE'}
          </span>
        </div>

        {scoreLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Score gauge */}
            <div className="text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#1a3a73" strokeWidth="12" />
                  <circle
                    cx="80" cy="80" r="70"
                    fill="none"
                    stroke={score?.score && score.score >= 80 ? '#ef4444' : score?.score >= 50 ? '#f97316' : '#06b6d4'}
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${(score?.score || 0) / 100 * 440} 440`}
                    transform="rotate(-90 80 80)"
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute text-center">
                  <div className={`text-4xl font-black ${riskColor}`}>
                    {score?.score || 0}
                  </div>
                  <div className="text-xs text-gray-500">/100</div>
                </div>
              </div>
              <p className="text-gray-400 text-sm mt-2">
                {score?.score === 0 ? 'No exposures found' : 'Privacy risk score'}
              </p>
            </div>

            {/* Breakdown */}
            <div className="space-y-3">
              {Object.entries(score?.breakdown || {}).map(([severity, count]) => (
                <div key={severity} className="flex items-center gap-3">
                  <span className={`text-xs font-bold uppercase w-16 badge-${severity} px-2 py-0.5 rounded`}>
                    {severity}
                  </span>
                  <div className="flex-1 bg-white/5 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${Math.min((count as number) * 10, 100)}%`,
                        backgroundColor: severityColors[severity as keyof typeof severityColors],
                      }}
                    />
                  </div>
                  <span className="text-white font-bold text-sm w-6 text-right">{count as number}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: 'Active Leaks',
            value: (score?.breakdown?.critical || 0) + (score?.breakdown?.high || 0),
            icon: AlertTriangle,
            color: 'text-red-400',
            bg: 'bg-red-500/10',
          },
          {
            label: 'Removed',
            value: takedowns?.items?.filter((t: any) => t.status === 'removed').length || 0,
            icon: CheckCircle,
            color: 'text-green-400',
            bg: 'bg-green-500/10',
          },
          {
            label: 'Pending Requests',
            value: takedowns?.items?.filter((t: any) => ['pending', 'sent'].includes(t.status)).length || 0,
            icon: Clock,
            color: 'text-yellow-400',
            bg: 'bg-yellow-500/10',
          },
          {
            label: 'Unread Alerts',
            value: notifications?.length || 0,
            icon: Bell,
            color: 'text-cyan-400',
            bg: 'bg-cyan-500/10',
          },
        ].map((stat) => (
          <div key={stat.label} className="glass-card p-4">
            <div className={`w-10 h-10 ${stat.bg} rounded-xl flex items-center justify-center mb-3`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <div className={`text-2xl font-black ${stat.color}`}>{stat.value}</div>
            <div className="text-gray-400 text-sm mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Recommendations */}
      {score?.recommendations && score.recommendations.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            Recommendations
          </h2>
          <ul className="space-y-2">
            {score.recommendations.map((rec: string, i: number) => (
              <li key={i} className="flex items-start gap-3 text-sm text-gray-300">
                <span className="text-cyan-400 mt-0.5">→</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recent Scans */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Scans</h2>
          <Link href="/dashboard/findings" className="text-cyan-400 text-sm hover:text-cyan-300 flex items-center gap-1">
            View all <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        {scans?.items?.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No scans yet. Start your first scan to discover exposures.</p>
            <Link href="/dashboard/scan" className="text-cyan-400 text-sm mt-2 inline-block hover:text-cyan-300">
              Start a scan →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scans?.items?.map((scan: any) => (
              <div key={scan.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                <div className="flex items-center gap-3">
                  <Eye className="w-4 h-4 text-cyan-400" />
                  <div>
                    <div className="text-sm text-white font-medium capitalize">{scan.scan_type} scan</div>
                    <div className="text-xs text-gray-500">{new Date(scan.created_at).toLocaleDateString()}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-400">{scan.total_findings} findings</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    scan.status === 'completed' ? 'badge-low' :
                    scan.status === 'running' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' :
                    'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                  }`}>
                    {scan.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
