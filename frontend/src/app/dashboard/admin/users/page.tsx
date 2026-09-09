'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/lib/api'
import { Users, Search, Loader2, Shield, UserX, UserCheck, ChevronLeft, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { formatDate } from '@/lib/utils'

const ROLE_COLORS: Record<string, string> = {
  admin:        'bg-purple-500/20 text-purple-400 border-purple-500/30',
  organization: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  individual:   'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
}

const STATUS_COLORS: Record<string, string> = {
  active:               'bg-green-500/20 text-green-400',
  inactive:             'bg-gray-500/20 text-gray-400',
  suspended:            'bg-red-500/20 text-red-400',
  pending_verification: 'bg-yellow-500/20 text-yellow-400',
}

export default function AdminUsersPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const PAGE_SIZE = 20

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, roleFilter, statusFilter],
    queryFn: async () => {
      const res = await adminApi.getUsers({
        page, page_size: PAGE_SIZE,
        ...(roleFilter   ? { role: roleFilter }   : {}),
        ...(statusFilter ? { status: statusFilter } : {}),
      })
      return res.data
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      adminApi.updateUserStatus(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-users'] }); toast.success('Status updated') },
    onError: () => toast.error('Failed to update status'),
  })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      adminApi.updateUserRole(id, role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-users'] }); toast.success('Role updated') },
    onError: () => toast.error('Failed to update role'),
  })

  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-cyan-400" /> User Management
          </h1>
          <p className="text-gray-400 text-sm mt-1">{data?.total || 0} total users</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(1) }}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
          <option value="">All Roles</option>
          <option value="individual">Individual</option>
          <option value="organization">Organization</option>
          <option value="admin">Admin</option>
        </select>
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="suspended">Suspended</option>
          <option value="pending_verification">Pending</option>
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-white/10">
                <tr className="text-left text-gray-500 text-xs">
                  {['Email', 'Name', 'Role', 'Status', 'MFA', 'Joined', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data?.items?.map((u: any) => (
                  <tr key={u.id} className="hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 text-white font-medium">{u.email}</td>
                    <td className="px-4 py-3 text-gray-400">{u.full_name || '—'}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={e => roleMutation.mutate({ id: u.id, role: e.target.value })}
                        className={`text-xs px-2 py-0.5 rounded border cursor-pointer bg-transparent ${ROLE_COLORS[u.role] || ''}`}
                      >
                        <option value="individual">Individual</option>
                        <option value="organization">Organization</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded capitalize ${STATUS_COLORS[u.status] || ''}`}>
                        {u.status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.mfa_enabled
                        ? <span className="text-xs text-green-400">✓ On</span>
                        : <span className="text-xs text-gray-600">Off</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {u.status !== 'active' && (
                          <button
                            onClick={() => statusMutation.mutate({ id: u.id, status: 'active' })}
                            className="p-1 text-green-400 hover:bg-green-500/10 rounded transition-colors"
                            title="Activate"
                          >
                            <UserCheck className="w-4 h-4" />
                          </button>
                        )}
                        {u.status !== 'suspended' && (
                          <button
                            onClick={() => {
                              if (window.confirm(`Suspend ${u.email}?`))
                                statusMutation.mutate({ id: u.id, status: 'suspended' })
                            }}
                            className="p-1 text-red-400 hover:bg-red-500/10 rounded transition-colors"
                            title="Suspend"
                          >
                            <UserX className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-white/10">
              <span className="text-xs text-gray-500">
                Page {page} of {totalPages} — {data?.total} users
              </span>
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
