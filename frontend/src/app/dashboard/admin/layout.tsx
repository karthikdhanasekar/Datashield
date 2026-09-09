'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart2, Users, FileText, Settings, ChevronRight } from 'lucide-react'

const adminNav = [
  { href: '/dashboard/admin',            icon: BarChart2, label: 'Analytics' },
  { href: '/dashboard/admin/users',      icon: Users,     label: 'Users' },
  { href: '/dashboard/admin/audit-logs', icon: FileText,  label: 'Audit Logs' },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const role = localStorage.getItem('user_role')
    if (role !== 'admin') {
      router.push('/dashboard')
    }
  }, [router])

  return (
    <div className="space-y-6">
      {/* Admin breadcrumb nav */}
      <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
        <Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-cyan-400">Admin</span>
        {pathname !== '/dashboard/admin' && (
          <>
            <ChevronRight className="w-3 h-3" />
            <span className="text-white capitalize">
              {pathname.split('/').pop()?.replace(/-/g, ' ')}
            </span>
          </>
        )}
      </div>

      {/* Admin sub-nav tabs */}
      <div className="flex gap-1 p-1 bg-white/5 rounded-xl w-fit">
        {adminNav.map(item => {
          const active = pathname === item.href
          return (
            <Link key={item.href} href={item.href}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}>
              <item.icon className="w-4 h-4" />
              {item.label}
            </Link>
          )
        })}
      </div>

      {children}
    </div>
  )
}
