'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { monitorApi } from '@/lib/api'
import {
  Activity, Plus, Trash2, CheckCircle, AlertTriangle,
  Clock, RefreshCw, Loader2, Bell, BellOff, ExternalLink
} from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'

const schema = z.object({
  target_url: z.string().url('Enter a valid URL (https://...)'),
  monitor_interval: z.enum(['daily', 'weekly', 'monthly']),
  alert_on_reappear: z.boolean(),
  alert_on_new_leak: z.boolean(),
})
type FormData = z.infer<typeof schema>

const STATUS_BADGE: Record<string, string> = {
  exposed:    'badge-critical',
  removed:    'badge-low',
  error:      'bg-gray-500/20 text-gray-400 border-gray-500/30 border',
  still_exposed: 'badge-high',
}

const INTERVAL_LABEL: Record<string, string> = {
  daily:   '⏰ Daily',
  weekly:  '📅 Weekly',
  monthly: '🗓 Monthly',
}

export default function MonitoringPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)

  const { data: monitors, isLoading } = useQuery({
    queryKey: ['monitors'],
    queryFn: async () => {
      const res = await monitorApi.list()
      return res.data as any[]
    },
    refetchInterval: 30000,
  })

  const createMutation = useMutation({
    mutationFn: (data: FormData) => monitorApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['monitors'] })
      toast.success('Monitor created')
      setShowForm(false)
      reset()
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => monitorApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['monitors'] })
      toast.success('Monitor removed')
    },
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      monitor_interval: 'weekly',
      alert_on_reappear: true,
      alert_on_new_leak: true,
    },
  })

  const activeCount = monitors?.filter((m: any) => m.is_active).length || 0
  const exposedCount = monitors?.filter((m: any) => m.last_status === 'exposed').length || 0
  const removedCount = monitors?.filter((m: any) => m.last_status === 'removed').length || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Monitoring</h1>
          <p className="text-gray-400 text-sm mt-1">
            Continuously watch URLs for data reappearance
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Monitor
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Active Monitors', value: activeCount, color: 'text-cyan-400', icon: Activity },
          { label: 'Still Exposed', value: exposedCount, color: 'text-red-400', icon: AlertTriangle },
          { label: 'Confirmed Removed', value: removedCount, color: 'text-green-400', icon: CheckCircle },
        ].map((s) => (
          <div key={s.label} className="glass-card p-4 text-center">
            <div className={`w-8 h-8 mx-auto mb-2 ${s.color}`}>
              <s.icon className="w-8 h-8" />
            </div>
            <div className={`text-2xl font-black ${s.color}`}>{s.value}</div>
            <div className="text-xs text-gray-400 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Add Monitor Form */}
      {showForm && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">New Monitor</h2>
          <form onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Target URL</label>
              <input
                {...register('target_url')}
                placeholder="https://example.com/page-with-my-data"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 text-sm"
              />
              {errors.target_url && (
                <p className="text-red-400 text-xs mt-1">{errors.target_url.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Check Interval</label>
                <select
                  {...register('monitor_interval')}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500 text-sm"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              <div className="space-y-2 pt-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" {...register('alert_on_reappear')}
                    className="w-4 h-4 accent-cyan-500" />
                  <span className="text-sm text-gray-300">Alert if data reappears</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" {...register('alert_on_new_leak')}
                    className="w-4 h-4 accent-cyan-500" />
                  <span className="text-sm text-gray-300">Alert on new leaks</span>
                </label>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-navy-950 font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
              >
                {createMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : <Plus className="w-4 h-4" />}
                Create Monitor
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); reset() }}
                className="px-5 py-2.5 text-sm text-gray-400 hover:text-white border border-white/10 hover:border-white/20 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Monitors list */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>
      ) : !monitors?.length ? (
        <div className="text-center py-16 text-gray-500">
          <Activity className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="mb-2">No active monitors.</p>
          <p className="text-sm">Add a monitor to track whether exposed data has been removed.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {monitors.map((m: any) => (
            <div key={m.id} className="glass-card p-5 hover:border-white/20 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {/* URL */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-medium text-sm truncate">{m.target_domain}</span>
                    <a
                      href={m.target_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-cyan-400 flex-shrink-0"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>

                  {/* Meta row */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span>{INTERVAL_LABEL[m.monitor_interval]}</span>

                    {m.last_status && (
                      <span className={`px-2 py-0.5 rounded text-xs ${STATUS_BADGE[m.last_status] || 'text-gray-400'}`}>
                        {m.last_status.replace(/_/g, ' ')}
                      </span>
                    )}

                    {m.last_checked_at && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Last checked: {new Date(m.last_checked_at).toLocaleDateString()}
                      </span>
                    )}

                    {m.next_check_at && (
                      <span>
                        Next: {new Date(m.next_check_at).toLocaleDateString()}
                      </span>
                    )}

                    {/* Alert icons */}
                    {m.alert_on_reappear ? (
                      <span title="Alerts enabled"><Bell className="w-3 h-3 text-cyan-400" /></span>
                    ) : (
                      <span title="Alerts disabled"><BellOff className="w-3 h-3 text-gray-600" /></span>
                    )}

                    {m.consecutive_failures > 0 && (
                      <span className="text-orange-400">
                        ⚠ {m.consecutive_failures} failure(s)
                      </span>
                    )}
                  </div>

                  {/* Full URL */}
                  <p className="text-xs text-gray-600 mt-1 truncate">{m.target_url}</p>
                </div>

                {/* Delete */}
                <button
                  onClick={() => {
                    if (window.confirm('Remove this monitor?')) {
                      deleteMutation.mutate(m.id)
                    }
                  }}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors flex-shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
