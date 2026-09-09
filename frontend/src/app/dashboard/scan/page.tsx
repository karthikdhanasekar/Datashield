'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import {
  Search, Mail, Phone, User, AtSign, CreditCard,
  MapPin, Shield, Loader2, CheckCircle, Info
} from 'lucide-react'
import { scanApi } from '@/lib/api'

const schema = z.object({
  scan_type: z.string().min(1, 'Select a scan type'),
  query_value: z.string().min(1, 'Enter a value to scan'),
  modules: z.array(z.string()).min(1, 'Select at least one module'),
})

type FormData = z.infer<typeof schema>

const SCAN_TYPES = [
  { value: 'email', label: 'Email Address', icon: Mail, placeholder: 'you@example.com', description: 'Check for breaches, social profiles, paste sites' },
  { value: 'phone', label: 'Phone Number', icon: Phone, placeholder: '+91 9876543210', description: 'Search for public listings and directories' },
  { value: 'name', label: 'Full Name', icon: User, placeholder: 'John Doe', description: 'Find public profiles and documents' },
  { value: 'username', label: 'Username', icon: AtSign, placeholder: 'johndoe123', description: 'Check all social platforms and paste sites' },
  { value: 'aadhaar', label: 'Aadhaar (masked)', icon: CreditCard, placeholder: 'XXXX-XXXX-1234', description: 'Search for government ID exposure (masked)' },
  { value: 'pan', label: 'PAN Card (masked)', icon: CreditCard, placeholder: 'ABCDE1234F', description: 'Search for PAN card exposure (masked)' },
  { value: 'address', label: 'Address', icon: MapPin, placeholder: '123 Main St, City', description: 'Check for address exposure in public records' },
]

const MODULES = [
  {
    value: 'breach',
    label: 'Breach Detection',
    description: 'XposedOrNot (17B+ records, free) + HIBP if key configured',
    badge: 'Free',
  },
  {
    value: 'holehe',
    label: 'Site Registration (Holehe)',
    description: 'Check if email is registered on 120+ platforms',
    badge: 'Free',
  },
  {
    value: 'maigret',
    label: 'Maigret Username Hunt',
    description: 'Username OSINT across 3,000+ sites — extracts bio, location',
    badge: 'Free',
  },
  {
    value: 'sherlock',
    label: 'Sherlock Username Hunt',
    description: 'Username search across 400+ social networks',
    badge: 'Free',
  },
  {
    value: 'social_media',
    label: 'Social Media Profiles',
    description: 'GitHub, Reddit, Twitter, Instagram, LinkedIn, Facebook',
    badge: 'Free',
  },
  {
    value: 'search_engine',
    label: 'Search Engine Dorks',
    description: 'Google and Bing indexed content, document exposure',
    badge: 'Key needed',
  },
  {
    value: 'darkweb',
    label: 'Dark Web Indicators',
    description: 'Ahmia.fi Tor index — check for dark web mentions',
    badge: 'Free',
  },
  {
    value: 'spiderfoot',
    label: 'SpiderFoot Modules',
    description: 'LeakIX breach data + Hunter.io email verification + DNS',
    badge: 'Free',
  },
  {
    value: 'paste',
    label: 'Paste Sites',
    description: 'Pastebin dump search (psbdmp)',
    badge: 'Free',
  },
  {
    value: 'document',
    label: 'Document Scanner',
    description: 'Public PDFs, spreadsheets, CSV files with your data',
    badge: 'Key needed',
  },
]

const BADGE_COLORS: Record<string, string> = {
  'Free':       'text-green-400 bg-green-500/10 border-green-500/20',
  'Key needed': 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
}

export default function ScanPage() {
  const router = useRouter()
  const [scanning, setScanning] = useState(false)
  const [selectedType, setSelectedType] = useState('')

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      modules: ['breach', 'holehe', 'maigret', 'sherlock', 'social_media', 'darkweb', 'spiderfoot', 'paste'],
    },
  })

  const selectedModules = watch('modules') || []
  const currentType = SCAN_TYPES.find(t => t.value === selectedType)

  const toggleModule = (value: string) => {
    const current = selectedModules
    const updated = current.includes(value)
      ? current.filter(m => m !== value)
      : [...current, value]
    setValue('modules', updated)
  }

  const onSubmit = async (data: FormData) => {
    setScanning(true)
    try {
      const res = await scanApi.create(data)
      toast.success('Scan started!')
      router.push(`/dashboard/scan/${res.data.id}`)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to start scan'
      toast.error(msg)
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">New OSINT Scan</h1>
        <p className="text-gray-400 text-sm mt-1">Search public sources for your exposed personal information</p>
      </div>

      {/* Ethics notice */}
      <div className="flex items-start gap-3 p-4 bg-cyan-500/10 border border-cyan-500/20 rounded-xl">
        <Shield className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-cyan-300">
          All scans are <strong>consent-based</strong> and search only publicly available information.
          Your data is encrypted and never shared. Searches are rate-limited to prevent abuse.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Scan Type Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-3">What do you want to scan?</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {SCAN_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => {
                  setSelectedType(type.value)
                  setValue('scan_type', type.value)
                }}
                className={`
                  flex flex-col items-start gap-2 p-4 rounded-xl border text-left transition-all
                  ${selectedType === type.value
                    ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                    : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:text-white'
                  }
                `}
              >
                <type.icon className="w-5 h-5" />
                <div>
                  <div className="text-sm font-medium">{type.label}</div>
                </div>
              </button>
            ))}
          </div>
          {errors.scan_type && <p className="text-red-400 text-xs mt-1">{errors.scan_type.message}</p>}
        </div>

        {/* Query Input */}
        {selectedType && (
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Enter {currentType?.label}
            </label>
            {currentType?.description && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2">
                <Info className="w-3 h-3" />
                {currentType.description}
              </div>
            )}
            <input
              {...register('query_value')}
              type="text"
              placeholder={currentType?.placeholder}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors"
            />
            {errors.query_value && <p className="text-red-400 text-xs mt-1">{errors.query_value.message}</p>}
          </div>
        )}

        {/* Modules */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-3">Scan Modules</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {MODULES.map((mod) => (
              <label
                key={mod.value}
                className={`
                  flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all
                  ${selectedModules.includes(mod.value)
                    ? 'border-cyan-500/40 bg-cyan-500/10'
                    : 'border-white/10 bg-white/5 hover:border-white/20'
                  }
                `}
              >
                <div className={`mt-0.5 w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                  selectedModules.includes(mod.value)
                    ? 'bg-cyan-500 border-cyan-500'
                    : 'border-white/20'
                }`}>
                  {selectedModules.includes(mod.value) && <CheckCircle className="w-3 h-3 text-navy-950" />}
                </div>
                <input
                  type="checkbox"
                  className="hidden"
                  checked={selectedModules.includes(mod.value)}
                  onChange={() => toggleModule(mod.value)}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-white">{mod.label}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${BADGE_COLORS[mod.badge] ?? ''}`}>
                      {mod.badge}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">{mod.description}</div>
                </div>
              </label>
            ))}
          </div>
          {errors.modules && <p className="text-red-400 text-xs mt-1">{errors.modules.message}</p>}
        </div>

        <button
          type="submit"
          disabled={scanning || !selectedType}
          className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-navy-950 font-bold py-4 rounded-xl text-lg transition-colors"
        >
          {scanning ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Search className="w-5 h-5" />
              Start OSINT Scan
            </>
          )}
        </button>
      </form>
    </div>
  )
}
