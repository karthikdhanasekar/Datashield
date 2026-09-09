'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scanApi, complaintApi } from '@/lib/api'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import {
  FileText, Download, Loader2, Shield, Globe,
  CheckCircle, Plus, AlertTriangle
} from 'lucide-react'
import { formatDate } from '@/lib/utils'

const schema = z.object({
  incident_summary: z.string().min(20, 'Provide at least 20 characters describing the incident'),
  jurisdiction:    z.string().optional(),
  authority_name:  z.string().optional(),
  authority_url:   z.string().url('Enter a valid URL').optional().or(z.literal('')),
})
type FormData = z.infer<typeof schema>

const JURISDICTIONS = [
  { name: 'India — Cyber Crime Portal',          url: 'https://cybercrime.gov.in',          authority: 'National Cyber Crime Reporting Portal (NCRP)' },
  { name: 'EU — Data Protection Authorities',     url: 'https://edpb.europa.eu/about-edpb/about-edpb/members_en', authority: 'European Data Protection Board' },
  { name: 'UK — ICO',                            url: 'https://ico.org.uk/make-a-complaint', authority: 'Information Commissioner\'s Office' },
  { name: 'USA — FTC',                           url: 'https://reportfraud.ftc.gov',         authority: 'Federal Trade Commission' },
  { name: 'Australia — OAIC',                    url: 'https://www.oaic.gov.au/privacy/privacy-complaints', authority: 'Office of the Australian Information Commissioner' },
  { name: 'Canada — OPC',                        url: 'https://www.priv.gc.ca/en/report-a-concern', authority: 'Office of the Privacy Commissioner' },
]

export default function ComplaintsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [selectedFindings, setSelectedFindings] = useState<string[]>([])

  const { data: scans } = useQuery({
    queryKey: ['scans', 'completed'],
    queryFn: async () => {
      const res = await scanApi.list({ status: 'completed', page_size: 5 })
      return res.data
    },
  })

  const latestScanId = scans?.items?.[0]?.id

  const { data: scanResult } = useQuery({
    queryKey: ['scan-findings-complaint', latestScanId],
    queryFn: async () => {
      if (!latestScanId) return null
      const res = await scanApi.get(latestScanId)
      return res.data
    },
    enabled: !!latestScanId,
  })

  const { register, handleSubmit, setValue, watch, formState: { errors }, reset } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const createMutation = useMutation({
    mutationFn: (data: FormData) => complaintApi.create({
      ...data,
      finding_ids: selectedFindings,
    }),
    onSuccess: (res) => {
      toast.success('Complaint package generated!')
      setShowForm(false)
      setSelectedFindings([])
      reset()
      qc.invalidateQueries({ queryKey: ['complaints'] })
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to create complaint'),
  })

  const toggleFinding = (id: string) => {
    setSelectedFindings(prev =>
      prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]
    )
  }

  const selectJurisdiction = (j: typeof JURISDICTIONS[0]) => {
    setValue('jurisdiction', j.name)
    setValue('authority_name', j.authority)
    setValue('authority_url', j.url)
  }

  const findings = scanResult?.findings?.filter((f: any) => !f.is_false_positive && !f.is_removed) || []

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Cybercrime Complaint Assistant</h1>
          <p className="text-gray-400 text-sm mt-1">
            Generate a formal complaint package for law enforcement or data protection authorities
          </p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors">
          <Plus className="w-4 h-4" /> New Complaint
        </button>
      </div>

      {/* Info notice */}
      <div className="p-4 bg-cyan-500/10 border border-cyan-500/20 rounded-xl flex items-start gap-3 text-sm text-cyan-300">
        <Shield className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          This assistant generates a downloadable complaint package — it does
          <strong> not automatically submit</strong> to authorities.
          You review and submit the package yourself to the appropriate authority.
        </div>
      </div>

      {showForm && (
        <div className="glass-card p-6 space-y-6">
          <h2 className="text-lg font-semibold text-white">Create Complaint Package</h2>

          {/* Step 1: Select findings */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-3">
              Step 1 — Select Findings to Include
              <span className="ml-2 text-xs text-gray-500">({selectedFindings.length} selected)</span>
            </h3>
            {findings.length === 0 ? (
              <div className="text-center py-6 text-gray-500 text-sm border border-white/10 rounded-xl">
                No active findings. Run a scan first.
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {findings.map((f: any) => (
                  <label key={f.id}
                    className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                      selectedFindings.includes(f.id)
                        ? 'border-cyan-500/40 bg-cyan-500/10'
                        : 'border-white/10 bg-white/5 hover:border-white/20'
                    }`}>
                    <input type="checkbox" className="mt-0.5 accent-cyan-500"
                      checked={selectedFindings.includes(f.id)}
                      onChange={() => toggleFinding(f.id)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded badge-${f.severity}`}>
                          {f.severity}
                        </span>
                        <span className="text-sm text-white truncate">{f.source_domain || 'Unknown'}</span>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{f.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Step 2: Incident summary */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">Step 2 — Incident Summary</h3>
            <textarea {...register('incident_summary')} rows={4}
              placeholder="Describe what happened: my personal data including [email/phone/documents] was found exposed on the internet without my consent. The exposure was discovered on [date]..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 text-sm resize-none" />
            {errors.incident_summary && (
              <p className="text-red-400 text-xs mt-1">{errors.incident_summary.message}</p>
            )}
          </div>

          {/* Step 3: Jurisdiction */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-3">Step 3 — Select Authority</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
              {JURISDICTIONS.map(j => (
                <button key={j.name} type="button" onClick={() => selectJurisdiction(j)}
                  className={`text-left p-3 rounded-xl border text-sm transition-all ${
                    watch('jurisdiction') === j.name
                      ? 'border-cyan-500 bg-cyan-500/10 text-white'
                      : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20'
                  }`}>
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                    <span className="font-medium">{j.name}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 ml-6">{j.authority}</p>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Authority Name</label>
                <input {...register('authority_name')} placeholder="Authority name"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Authority URL</label>
                <input {...register('authority_url')} placeholder="https://..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500" />
                {errors.authority_url && (
                  <p className="text-red-400 text-xs mt-1">{errors.authority_url.message}</p>
                )}
              </div>
            </div>
          </div>

          {/* Submit */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={handleSubmit(d => createMutation.mutate(d))}
              disabled={createMutation.isPending || selectedFindings.length === 0}
              className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-navy-950 font-bold px-6 py-3 rounded-xl transition-colors">
              {createMutation.isPending
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                : <><FileText className="w-4 h-4" /> Generate Package</>
              }
            </button>
            <button type="button" onClick={() => { setShowForm(false); reset(); setSelectedFindings([]) }}
              className="px-6 py-3 text-sm text-gray-400 hover:text-white border border-white/10 hover:border-white/20 rounded-xl transition-colors">
              Cancel
            </button>
          </div>
          {selectedFindings.length === 0 && (
            <p className="text-xs text-yellow-400 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Select at least one finding to include
            </p>
          )}
        </div>
      )}

      {/* How it works */}
      {!showForm && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { step: '1', title: 'Select Findings', desc: 'Choose which exposures to include in your complaint' },
              { step: '2', title: 'Write Summary', desc: 'Describe the incident in plain language' },
              { step: '3', title: 'Choose Authority', desc: 'Select the relevant law enforcement or data authority' },
              { step: '4', title: 'Download Package', desc: 'Get a formatted complaint with all evidence attached' },
            ].map(s => (
              <div key={s.step} className="text-center">
                <div className="w-10 h-10 bg-cyan-500/20 text-cyan-400 font-black text-lg rounded-full flex items-center justify-center mx-auto mb-2">
                  {s.step}
                </div>
                <div className="text-white text-sm font-medium">{s.title}</div>
                <div className="text-gray-500 text-xs mt-1">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
