'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/lib/api'
import { User, Shield, Bell, Key, Loader2, CheckCircle, QrCode, Copy, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import QRCode from 'qrcode.react'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'notifications'>('profile')
  const [mfaSetup, setMfaSetup] = useState<any>(null)
  const [mfaCode, setMfaCode] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[]>([])

  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await authApi.getMe()
      return res.data
    },
  })

  const setupMfaMutation = useMutation({
    mutationFn: () => authApi.setupMFA(),
    onSuccess: (res) => setMfaSetup(res.data),
    onError: () => toast.error('Failed to start MFA setup'),
  })

  const verifyMfaMutation = useMutation({
    mutationFn: (code: string) => authApi.verifyMFA(code),
    onSuccess: (res) => {
      setBackupCodes(res.data.backup_codes || [])
      toast.success('MFA enabled successfully!')
      setMfaSetup(null)
    },
    onError: () => toast.error('Invalid code. Try again.'),
  })

  const disableMfaMutation = useMutation({
    mutationFn: (code: string) => authApi.disableMFA(code),
    onSuccess: () => {
      toast.success('MFA disabled')
      setMfaCode('')
    },
    onError: () => toast.error('Invalid code'),
  })

  if (isLoading) return (
    <div className="flex justify-center py-20">
      <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
    </div>
  )

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security & MFA', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ]

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 text-sm mt-1">Manage your account and security preferences</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-white/5 rounded-xl">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">Account Information</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500">Email</label>
              <div className="text-white mt-1">{me?.email}</div>
            </div>
            <div>
              <label className="text-xs text-gray-500">Full Name</label>
              <div className="text-white mt-1">{me?.full_name || '—'}</div>
            </div>
            <div>
              <label className="text-xs text-gray-500">Role</label>
              <div className="mt-1">
                <span className="text-xs capitalize bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 px-2 py-1 rounded">
                  {me?.role}
                </span>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500">Account Status</label>
              <div className="mt-1">
                <span className={`text-xs capitalize px-2 py-1 rounded ${
                  me?.status === 'active'
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-gray-500/20 text-gray-400'
                }`}>
                  {me?.status}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="space-y-4">
          {/* MFA Status */}
          <div className="glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-white">Two-Factor Authentication</h2>
                <p className="text-sm text-gray-400 mt-1">
                  Add an extra layer of security with an authenticator app
                </p>
              </div>
              <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                me?.mfa_enabled
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-gray-500/20 text-gray-400'
              }`}>
                {me?.mfa_enabled ? '✓ Enabled' : 'Disabled'}
              </span>
            </div>

            {!me?.mfa_enabled && !mfaSetup && (
              <button
                onClick={() => setupMfaMutation.mutate()}
                disabled={setupMfaMutation.isPending}
                className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
              >
                {setupMfaMutation.isPending
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <QrCode className="w-4 h-4" />}
                Set Up MFA
              </button>
            )}

            {/* MFA Setup Flow */}
            {mfaSetup && (
              <div className="space-y-4">
                <div className="text-sm text-gray-300">
                  Scan this QR code with Google Authenticator, Authy, or any TOTP app:
                </div>
                <div className="flex justify-center p-4 bg-white rounded-xl w-fit mx-auto">
                  <QRCode value={mfaSetup.provisioning_uri} size={180} />
                </div>
                <div className="text-xs text-gray-500 text-center">
                  Can't scan? Enter manually: <span className="text-cyan-400 font-mono">{mfaSetup.secret}</span>
                </div>
                <div className="flex gap-3">
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="Enter 6-digit code"
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white text-center text-xl tracking-widest focus:outline-none focus:border-cyan-500"
                  />
                  <button
                    onClick={() => verifyMfaMutation.mutate(mfaCode)}
                    disabled={mfaCode.length < 6 || verifyMfaMutation.isPending}
                    className="bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-navy-950 font-semibold px-4 py-2.5 rounded-lg transition-colors"
                  >
                    {verifyMfaMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify'}
                  </button>
                </div>
              </div>
            )}

            {/* Backup codes */}
            {backupCodes.length > 0 && (
              <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
                <p className="text-yellow-400 text-sm font-semibold mb-2">
                  ⚠ Save these backup codes — they won't be shown again:
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {backupCodes.map((code) => (
                    <code key={code} className="text-xs font-mono text-white bg-white/5 px-3 py-1.5 rounded">
                      {code}
                    </code>
                  ))}
                </div>
              </div>
            )}

            {/* Disable MFA */}
            {me?.mfa_enabled && !mfaSetup && (
              <div className="mt-4 pt-4 border-t border-white/10">
                <p className="text-sm text-gray-400 mb-3">
                  To disable MFA, enter your current authenticator code:
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    maxLength={6}
                    placeholder="000000"
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white text-center tracking-widest focus:outline-none focus:border-red-500"
                  />
                  <button
                    onClick={() => disableMfaMutation.mutate(mfaCode)}
                    disabled={mfaCode.length < 6 || disableMfaMutation.isPending}
                    className="bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 font-semibold px-4 py-2.5 rounded-lg transition-colors disabled:opacity-40"
                  >
                    Disable MFA
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="space-y-4">
          {/* Notification channels */}
          <div className="glass-card p-6 space-y-4">
            <h2 className="text-lg font-semibold text-white">Notification Preferences</h2>
            <p className="text-sm text-gray-400">Choose how you receive alerts for new exposures.</p>
            <div className="space-y-3">
              {[
                { label: 'Email Notifications', description: 'Receive breach alerts via email (requires SMTP config)', key: 'notification_email' },
                { label: 'SMS Notifications', description: 'Critical alerts via SMS (requires Twilio config)', key: 'notification_sms' },
                { label: 'In-App Notifications', description: 'Push notifications inside DataShield', key: 'notification_push' },
              ].map((pref) => (
                <div key={pref.key} className="flex items-start justify-between p-3 bg-white/5 rounded-lg">
                  <div>
                    <div className="text-sm font-medium text-white">{pref.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{pref.description}</div>
                  </div>
                  <div className={`w-10 h-6 rounded-full flex items-center px-1 transition-colors ${
                    me?.[pref.key] ? 'bg-cyan-500 justify-end' : 'bg-white/10 justify-start'
                  }`}>
                    <div className="w-4 h-4 bg-white rounded-full" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Telegram setup */}
          <div className="glass-card p-6 space-y-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-white">Telegram Alerts</h2>
              <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-2 py-0.5 rounded">Free</span>
            </div>
            <p className="text-sm text-gray-400">
              Get instant breach alerts on Telegram — no API cost, instant delivery.
            </p>
            <div className="p-4 bg-white/5 rounded-xl space-y-3 text-sm">
              <div className="flex items-start gap-3">
                <span className="text-cyan-400 font-bold flex-shrink-0">1.</span>
                <span className="text-gray-300">
                  Open Telegram → message <span className="font-mono text-cyan-400">@BotFather</span> → type <span className="font-mono text-white">/newbot</span>
                </span>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-cyan-400 font-bold flex-shrink-0">2.</span>
                <span className="text-gray-300">
                  Copy the token and add to <span className="font-mono text-white">.env</span>:<br />
                  <span className="font-mono text-cyan-400 text-xs">TELEGRAM_BOT_TOKEN=your-bot-token</span>
                </span>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-cyan-400 font-bold flex-shrink-0">3.</span>
                <span className="text-gray-300">
                  Start a chat with your bot, then visit:<br />
                  <span className="font-mono text-xs text-gray-400">
                    https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates
                  </span><br />
                  Find your <span className="font-mono text-white">chat_id</span> and add to <span className="font-mono text-white">.env</span>:<br />
                  <span className="font-mono text-cyan-400 text-xs">TELEGRAM_DEFAULT_CHAT_ID=123456789</span>
                </span>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-cyan-400 font-bold flex-shrink-0">4.</span>
                <span className="text-gray-300">
                  Restart containers: <span className="font-mono text-xs text-white">docker compose ... up -d --force-recreate backend celery_worker</span>
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-600">
              Once configured, you'll get a Telegram message every time a scan finds critical or high-severity exposures.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
