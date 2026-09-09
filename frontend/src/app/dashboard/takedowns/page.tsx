'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { takedownApi } from '@/lib/api'
import { FileText, Clock, CheckCircle, XCircle, AlertTriangle, Send, ChevronDown, Loader2 } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  sent: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  acknowledged: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  in_progress: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  removed: 'bg-green-500/20 text-green-400 border-green-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
  escalated: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
}

const STATUS_ICONS: Record<string, any> = {
  pending: Clock,
  sent: Send,
  acknowledged: CheckCircle,
  in_progress: AlertTriangle,
  removed: CheckCircle,
  rejected: XCircle,
  escalated: AlertTriangle,
  failed: XCircle,
}

export default function TakedownsPage() {
  const qc = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')

  const { data, isLoading } = useQuery({
    queryKey: ['takedowns', filter],
    queryFn: async () => {
      const params: any = { page_size: 50 }
      if (filter !== 'all') params.status = filter
      const res = await takedownApi.list(params)
      return res.data
    },
  })

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: string; note?: string }) =>
      takedownApi.updateStatus(id, { status, note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['takedowns'] })
      toast.success('Status updated')
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Update failed'),
  })

  const statuses = ['all', 'pending', 'sent', 'acknowledged', 'in_progress', 'removed', 'rejected', 'escalated']

  if (isLoading) {
    return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
  }

  const items = data?.items || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Takedown Requests</h1>
        <p className="text-gray-400 text-sm mt-1">Track your data removal requests and their status</p>
      </div>

      {/* Status filter tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {statuses.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-full border capitalize transition-colors ${
              filter === s
                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                : 'border-white/10 text-gray-400 hover:border-white/20'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Sent', count: items.filter((t: any) => t.status === 'sent').length, color: 'text-blue-400' },
          { label: 'Removed', count: items.filter((t: any) => t.status === 'removed').length, color: 'text-green-400' },
          { label: 'Pending', count: items.filter((t: any) => t.status === 'pending').length, color: 'text-yellow-400' },
          { label: 'Escalated', count: items.filter((t: any) => t.status === 'escalated').length, color: 'text-orange-400' },
        ].map((stat) => (
          <div key={stat.label} className="glass-card p-3 text-center">
            <div className={`text-2xl font-black ${stat.color}`}>{stat.count}</div>
            <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Takedown list */}
      {items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No takedown requests yet. Go to Findings to request removal.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item: any) => {
            const StatusIcon = STATUS_ICONS[item.status] || Clock
            const isExpanded = expandedId === item.id
            return (
              <div key={item.id} className="glass-card overflow-hidden">
                <button
                  className="w-full flex items-center gap-4 p-5 text-left hover:bg-white/5 transition-colors"
                  onClick={() => setExpandedId(isExpanded ? null : item.id)}
                >
                  <StatusIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-white font-medium text-sm truncate">{item.target_domain}</span>
                      <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_STYLES[item.status] || STATUS_STYLES.pending}`}>
                        {item.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {item.template_type.replace(/_/g, ' ')} • {item.contact_email || 'No contact email'} • {new Date(item.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </button>

                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-white/10 pt-4 space-y-4">
                    <div>
                      <div className="text-xs text-gray-500 mb-1">Subject</div>
                      <div className="text-sm text-white">{item.subject}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">Email Body</div>
                      <pre className="text-xs text-gray-300 bg-white/5 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap font-sans">
                        {item.body}
                      </pre>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-2">Update Status</div>
                      <div className="flex flex-wrap gap-2">
                        {['acknowledged', 'in_progress', 'removed', 'rejected'].map((s) => (
                          <button
                            key={s}
                            onClick={() => updateStatusMutation.mutate({ id: item.id, status: s })}
                            disabled={item.status === s || updateStatusMutation.isPending}
                            className="text-xs px-3 py-1.5 rounded-lg border border-white/10 hover:border-cyan-500/40 text-gray-400 hover:text-cyan-400 capitalize transition-colors disabled:opacity-40"
                          >
                            Mark as {s.replace(/_/g, ' ')}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
