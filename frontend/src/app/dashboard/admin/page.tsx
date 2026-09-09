'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/api'
import {
  Users, Shield, AlertTriangle, CheckCircle,
  TrendingUp, Activity, FileText, Loader2,
  BarChart2, Clock
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis,
  YAxis, Tooltip, BarChart, Bar, Cell
} from 'recharts'

const SEV_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
}

export default function AdminPage() {
  const router = useRouter()

  useEffect(() => {
    const role = localStorage.getItem('user_role')
    if (role !== 'admin') router.push('/dashboard')
  }, [router])

  const { data: overview, isLoading: ovLoading } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: async () => {
      const res = await adminApi.getAnalytics()
      return res.data
    },
  })

  const { data: trends, isLoading: trendLoading } = useQuery({
    queryKey: ['admin-trends'],
    queryFn: async () => {
      const res = await adminApi.getExposureTrends(30)
      return res.data
    },
  })

  const { data: users } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const res = await adminApi.getUsers({ page_size: 10 })
      return res.data
    },
  })

  if (ovLoading) {
    return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
  }

  const stats = [
    { label: 'Total Users',        value: overview?.total_users,          icon: Users,         color: 'text-cyan-400',   bg: 'bg-cyan-500/10' },
    { label: 'Active Users',       value: overview?.active_users,         icon: Activity,      color: 'text-green-400',  bg: 'bg-green-500/10' },
    { label: 'Total Scans',        value: overview?.total_scans,          icon: Shield,        color: 'text-blue-400',   bg: 'bg-blue-500/10' },
    { label: 'Scans (30d)',        value: overview?.recent_scans_30d,     icon: TrendingUp,    color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { label: 'Active Findings',    value: overview?.active_findings,      icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10' },
    { label: 'Removed',            value: overview?.removed_findings,     icon: CheckCircle,   color: 'text-green-400',  bg: 'bg-green-500/10' },
    { label: 'Takedowns Sent',     value: overview?.total_takedowns,      icon: FileText,      color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    { label: 'Removal Success %',  value: `${overview?.removal_success_rate}%`, icon: BarChart2, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
  ]

  // Build trend chart data
  const trendData = (trends?.trends || []).reduce((acc: any[], item: any) => {
    const date = item.date?.split('T')[0]
    const existing = acc.find((d) => d.date === date)
    if (existing) {
      existing[item.severity] = (existing[item.severity] || 0) + item.count
    } else {
      acc.push({ date, [item.severity]: item.count })
    }
    return acc
  }, [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Admin Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">Platform analytics and user management</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="glass-card p-4">
            <div className={`w-9 h-9 ${s.bg} rounded-lg flex items-center justify-center mb-3`}>
              <s.icon className={`w-5 h-5 ${s.color}`} />
            </div>
            <div className={`text-2xl font-black ${s.color}`}>{s.value ?? '—'}</div>
            <div className="text-xs text-gray-400 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Exposure trend chart */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-cyan-400" />
          Exposure Discovery Trend (30 days)
        </h2>
        {trendLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
        ) : trendData.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">No trend data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={trendData}>
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ background: '#0f2040', border: '1px solid rgba(6,182,212,0.2)', borderRadius: 8 }}
                labelStyle={{ color: '#fff' }}
              />
              {['critical', 'high', 'medium', 'low'].map((sev) => (
                <Area
                  key={sev}
                  type="monotone"
                  dataKey={sev}
                  stackId="1"
                  stroke={SEV_COLORS[sev]}
                  fill={SEV_COLORS[sev]}
                  fillOpacity={0.3}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Recent users */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            Recent Users
          </h2>
          <a href="/dashboard/admin/users" className="text-xs text-cyan-400 hover:text-cyan-300">
            View all →
          </a>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs border-b border-white/10">
                <th className="pb-3 font-medium">Email</th>
                <th className="pb-3 font-medium">Role</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">MFA</th>
                <th className="pb-3 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {users?.items?.map((u: any) => (
                <tr key={u.id} className="hover:bg-white/5 transition-colors">
                  <td className="py-3 text-white">{u.email}</td>
                  <td className="py-3">
                    <span className="text-xs px-2 py-0.5 rounded capitalize bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      {u.role}
                    </span>
                  </td>
                  <td className="py-3">
                    <span className={`text-xs px-2 py-0.5 rounded capitalize ${
                      u.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-gray-400'
                    }`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="py-3">
                    {u.mfa_enabled
                      ? <span className="text-xs text-green-400">✓ On</span>
                      : <span className="text-xs text-gray-500">Off</span>
                    }
                  </td>
                  <td className="py-3 text-gray-500 text-xs">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
