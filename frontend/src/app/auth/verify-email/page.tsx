'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { authApi } from '@/lib/api'
import { Shield, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'

function VerifyEmailContent() {
  const params = useSearchParams()
  const token = params.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) { setStatus('error'); setMessage('No verification token provided.'); return }
    authApi.verifyEmail(token)
      .then(() => { setStatus('success'); setMessage('Your email has been verified. You can now sign in.') })
      .catch((err) => { setStatus('error'); setMessage(err?.response?.data?.detail || 'Verification failed or token expired.') })
  }, [token])

  return (
    <div className="min-h-screen bg-navy-950 cyber-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md text-center">
        <div className="inline-flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-cyan-500 rounded-xl flex items-center justify-center">
            <Shield className="w-6 h-6 text-navy-950" />
          </div>
          <span className="text-2xl font-black text-white">DataShield <span className="text-cyan-400">OSINT</span></span>
        </div>

        <div className="glass-card p-8">
          {status === 'loading' && (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-12 h-12 animate-spin text-cyan-400" />
              <p className="text-gray-400">Verifying your email...</p>
            </div>
          )}
          {status === 'success' && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Email Verified!</h1>
              <p className="text-gray-400">{message}</p>
              <Link href="/auth/login"
                className="mt-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold px-8 py-3 rounded-xl transition-colors inline-block">
                Sign In Now
              </Link>
            </div>
          )}
          {status === 'error' && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center">
                <XCircle className="w-8 h-8 text-red-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Verification Failed</h1>
              <p className="text-gray-400">{message}</p>
              <Link href="/auth/register"
                className="mt-2 text-cyan-400 hover:text-cyan-300 transition-colors">
                Back to Register →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-navy-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
