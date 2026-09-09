'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Shield, LayoutDashboard, Search, FileText, Bell,
  Settings, LogOut, Menu, X, AlertTriangle, Activity,
  Bot, Users, ChevronDown, User, SearchCheck, Download
} from 'lucide-react'
import { authApi, notificationApi } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'

const navItems = [
  { href: '/dashboard',               icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/dashboard/scan',          icon: Search,          label: 'New Scan' },
  { href: '/dashboard/findings',      icon: AlertTriangle,   label: 'Findings' },
  { href: '/dashboard/search',        icon: SearchCheck,     label: 'Search' },
  { href: '/dashboard/takedowns',     icon: FileText,        label: 'Takedowns' },
  { href: '/dashboard/monitoring',    icon: Activity,        label: 'Monitoring' },
  { href: '/dashboard/reports',       icon: FileText,        label: 'Reports' },
  { href: '/dashboard/complaints',    icon: Bot,             label: 'Complaints' },
  { href: '/dashboard/ai-advisor',    icon: Bot,             label: 'AI Advisor' },
  { href: '/dashboard/notifications', icon: Bell,            label: 'Notifications' },
  { href: '/dashboard/settings',      icon: Settings,        label: 'Settings' },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  // Auth guard
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      router.push('/auth/login')
    }
  }, [router])

  const { data: unreadCount } = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: async () => {
      const res = await notificationApi.list({ unread_only: true })
      return res.data.length
    },
    refetchInterval: 30000,
  })

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {}
    localStorage.clear()
    toast.success('Logged out')
    router.push('/auth/login')
  }

  return (
    <div className="min-h-screen bg-navy-950 flex">
      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-navy-900 border-r border-white/10 z-30
        transform transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0 lg:static lg:block
      `}>
        {/* Logo */}
        <div className="p-6 border-b border-white/10">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-navy-950" />
            </div>
            <div>
              <div className="text-sm font-bold text-white">DataShield</div>
              <div className="text-xs text-cyan-400">OSINT Platform</div>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1 flex-1">
          {navItems.map((item) => {
            const active = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors relative
                  ${active
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
                {item.label === 'Notifications' && unreadCount && unreadCount > 0 && (
                  <span className="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        {/* User menu (bottom of sidebar) */}
        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors w-full"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 lg:ml-0">
        {/* Top bar */}
        <header className="border-b border-white/10 px-6 py-4 flex items-center justify-between bg-navy-900/50 backdrop-blur-sm sticky top-0 z-10">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-2 rounded-lg hover:bg-white/5 text-gray-400"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <div className="flex items-center gap-2 ml-auto">
            {/* Notifications bell */}
            <Link
              href="/dashboard/notifications"
              className="relative p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
            >
              <Bell className="w-5 h-5" />
              {unreadCount && unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </Link>

            {/* User avatar */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/5 cursor-pointer">
              <div className="w-7 h-7 bg-cyan-500/20 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-cyan-400" />
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
