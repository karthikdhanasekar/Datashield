'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationApi } from '@/lib/api'
import {
  Bell, CheckCheck, AlertTriangle, Shield,
  Activity, XCircle, Info, Loader2
} from 'lucide-react'
import toast from 'react-hot-toast'

const TYPE_ICONS: Record<string, any> = {
  new_exposure:         AlertTriangle,
  takedown_sent:        Shield,
  takedown_success:     CheckCheck,
  escalation_required:  XCircle,
  monitor_alert:        Activity,
  info:                 Info,
}

const SEV_COLORS: Record<string, string> = {
  critical: 'border-l-red-500 bg-red-500/5',
  warning:  'border-l-orange-500 bg-orange-500/5',
  info:     'border-l-cyan-500 bg-cyan-500/5',
}

export default function NotificationsPage() {
  const qc = useQueryClient()

  const { data: notifications, isLoading } = useQuery({
    queryKey: ['notifications', 'all'],
    queryFn: async () => {
      const res = await notificationApi.list()
      return res.data as any[]
    },
    refetchInterval: 30000,
  })

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const markAllMutation = useMutation({
    mutationFn: () => notificationApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      toast.success('All notifications marked as read')
    },
  })

  const unread = notifications?.filter((n: any) => !n.is_read).length || 0

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell className="w-6 h-6 text-cyan-400" />
            Notifications
            {unread > 0 && (
              <span className="text-sm bg-red-500 text-white px-2 py-0.5 rounded-full">
                {unread}
              </span>
            )}
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Alerts for exposures, takedowns, and monitoring events
          </p>
        </div>
        {unread > 0 && (
          <button
            onClick={() => markAllMutation.mutate()}
            disabled={markAllMutation.isPending}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white border border-white/10 hover:border-cyan-500/40 px-4 py-2 rounded-lg transition-colors"
          >
            {markAllMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <CheckCheck className="w-4 h-4" />
            }
            Mark all read
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>
      ) : !notifications?.length ? (
        <div className="text-center py-16 text-gray-500">
          <Bell className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No notifications yet.</p>
          <p className="text-sm mt-1">You'll be alerted when scans complete, data is found, or takedowns are processed.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n: any) => {
            const Icon = TYPE_ICONS[n.notification_type] || Bell
            const colorClass = SEV_COLORS[n.severity] || SEV_COLORS.info
            return (
              <div
                key={n.id}
                className={`glass-card border-l-4 p-4 transition-all cursor-pointer hover:bg-white/5 ${colorClass} ${
                  n.is_read ? 'opacity-60' : ''
                }`}
                onClick={() => {
                  if (!n.is_read) markReadMutation.mutate(n.id)
                }}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    n.severity === 'critical' ? 'bg-red-500/20' :
                    n.severity === 'warning'  ? 'bg-orange-500/20' : 'bg-cyan-500/20'
                  }`}>
                    <Icon className={`w-4 h-4 ${
                      n.severity === 'critical' ? 'text-red-400' :
                      n.severity === 'warning'  ? 'text-orange-400' : 'text-cyan-400'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-sm font-semibold ${n.is_read ? 'text-gray-400' : 'text-white'}`}>
                        {n.title}
                      </span>
                      <span className="text-xs text-gray-500 flex-shrink-0">
                        {new Date(n.created_at).toLocaleDateString()} {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 mt-0.5 leading-relaxed">{n.message}</p>
                  </div>
                  {!n.is_read && (
                    <div className="w-2 h-2 bg-cyan-400 rounded-full mt-2 flex-shrink-0" />
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
