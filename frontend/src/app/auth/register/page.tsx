'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Shield, Eye, EyeOff, Lock, Mail, User, Phone, Loader2, CheckCircle } from 'lucide-react'
import { authApi } from '@/lib/api'

const schema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Enter a valid email'),
  phone_number: z.string().optional(),
  password: z.string()
    .min(8, 'At least 8 characters')
    .regex(/[A-Z]/, 'At least one uppercase letter')
    .regex(/[a-z]/, 'At least one lowercase letter')
    .regex(/\d/, 'At least one number')
    .regex(/[!@#$%^&*]/, 'At least one special character'),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, {
  message: "Passwords don't match",
  path: ['confirm_password'],
})

type FormData = z.infer<typeof schema>

export default function RegisterPage() {
  const router = useRouter()
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const password = watch('password', '')

  const checks = [
    { label: '8+ characters', ok: password.length >= 8 },
    { label: 'Uppercase', ok: /[A-Z]/.test(password) },
    { label: 'Number', ok: /\d/.test(password) },
    { label: 'Special character', ok: /[!@#$%^&*]/.test(password) },
  ]

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      await authApi.register({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        phone_number: data.phone_number || undefined,
      })
      setDone(true)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-navy-950 cyber-bg flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-3">Check your email</h1>
          <p className="text-gray-400 mb-6">
            We&apos;ve sent a verification link to your email address. Click the link to activate your account.
          </p>
          <Link href="/auth/login" className="text-cyan-400 hover:text-cyan-300 transition-colors">
            Back to Sign In →
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-navy-950 cyber-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-cyan-500 rounded-xl flex items-center justify-center">
              <Shield className="w-6 h-6 text-navy-950" />
            </div>
            <span className="text-2xl font-black text-white">DataShield <span className="text-cyan-400">OSINT</span></span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Create account</h1>
          <p className="text-gray-400">Start protecting your privacy today</p>
        </div>

        <div className="glass-card p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Full Name */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input {...register('full_name')} placeholder="John Doe"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-10 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors" />
              </div>
              {errors.full_name && <p className="text-red-400 text-xs mt-1">{errors.full_name.message}</p>}
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input {...register('email')} type="email" placeholder="you@example.com"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-10 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors" />
              </div>
              {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Phone <span className="text-gray-500 font-normal">(optional)</span></label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input {...register('phone_number')} placeholder="+91 9876543210"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-10 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors" />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input {...register('password')} type={showPass ? 'text' : 'password'} placeholder="••••••••"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-10 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors" />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {password && (
                <div className="grid grid-cols-2 gap-1 mt-2">
                  {checks.map(c => (
                    <div key={c.label} className={`flex items-center gap-1 text-xs ${c.ok ? 'text-green-400' : 'text-gray-500'}`}>
                      <CheckCircle className="w-3 h-3" />
                      {c.label}
                    </div>
                  ))}
                </div>
              )}
              {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input {...register('confirm_password')} type="password" placeholder="••••••••"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-10 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors" />
              </div>
              {errors.confirm_password && <p className="text-red-400 text-xs mt-1">{errors.confirm_password.message}</p>}
            </div>

            <button type="submit" disabled={loading}
              className="w-full bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-navy-950 font-bold py-3 rounded-lg transition-colors flex items-center justify-center gap-2">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : null}
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-400">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
