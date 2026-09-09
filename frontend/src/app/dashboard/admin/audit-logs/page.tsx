'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/api'
import { FileText, Loader2, ChevronLeft, ChevronRight, CheckCircle, XCircle } from 'lucide-react'
import { formatDateTime } from '@/lib/utils'

export default function AuditLogsPage() {
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')
  const PAGE_SIZE = 30

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, actionFilter],
    queryFn: async () => {
      const res = await adminApi.getAuditLogs({
        page, page_size: PAGE_SIZE,
        ...(actionFilter ? { action: actionFilter } : {}),
      })
      return res.data
    },
  })

  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE)

  const COMMON_ACTIONS = [
    'user_register', 'login_success', 'login_failed', 'logout',
    'mfa_failed', 'scan_created', 'takedown_created',
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <FileText className="w-6 h-6 text-cyan-400" /> Audit Logs
        </h1>
        <p className="text-gray-400 text-sm mt-1">All platform actions — {data?.total || 0} total entries</p>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setActionFilter(''); setPage(1) }}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${!actionFilter ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400' : 'border-white/10 text-gray-400 hover:border-white/20'}`}>
          All
        </button>
        {COMMON_ACTIONS.map(a => (
          <button key={a} onClick={() => { setActionFilter(a); setPage(1) }}
            className={`text-xs px-3 py-1.5 rounded-full border capitalize transition-colors ${actionFilter === a ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400' : 'border-white/10 text-gray-400 hover:border-white/20'}`}>
            {a.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-white/10">
                <tr className="text-left text-gray-500 text-xs">
                  {['Time', 'User', 'Action', 'IP Address', 'Status'].map(h => (
                    <th key={h} className="px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data?.items?.map((log: any) => (
                  <tr key={log.id} className="hover:bg-white/5 transition-colors">
                    <td className="px-4 py-2.5 text-gray-500 text-xs whitespace-nowrap">
                      {formatDateTime(log.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs">
                      {log.user_id ? log.user_id.slice(0, 8) + '...' : 'System'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs text-white font-medium capitalize">
                        {log.action?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-500 text-xs font-mono">
                      {log.ip_address || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      {log.status === 'success'
                        ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle className="w-3 h-3" /> OK</span>
                        : <span className="flex items-center gap-1 text-xs text-red-400"><XCircle className="w-3 h-3" /> Failed</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-white/10">
              <span className="text-xs text-gray-500">Page {page} of {totalPages}</span>
              <div className="flex items-center gap-2">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="p-1 rounded text-gray-400 hover:text-white disabled:opacity-30">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  className="p-1 rounded text-gray-400 hover:text-white disabled:opacity-30">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
