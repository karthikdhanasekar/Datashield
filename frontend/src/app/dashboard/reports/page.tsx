'use client'

import { useQuery } from '@tanstack/react-query'
import { scanApi } from '@/lib/api'
import { FileText, Download, Loader2, Shield, Calendar, Hash } from 'lucide-react'

export default function ReportsPage() {
  const { data: scans, isLoading } = useQuery({
    queryKey: ['scans', 'completed'],
    queryFn: async () => {
      const res = await scanApi.list({ status: 'completed', page_size: 20 })
      return res.data
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Evidence Reports</h1>
        <p className="text-gray-400 text-sm mt-1">
          Download PDF, JSON, or CSV evidence packages for legal use
        </p>
      </div>

      <div className="p-4 bg-cyan-500/10 border border-cyan-500/20 rounded-xl text-sm text-cyan-300 flex items-start gap-3">
        <Shield className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <span>
          All reports include an <strong>evidence hash (SHA-256)</strong> for integrity verification.
          Reports are stored securely and auto-expire after 90 days.
        </span>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        </div>
      ) : !scans?.items?.length ? (
        <div className="text-center py-16 text-gray-500">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No completed scans yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {scans.items.map((scan: any) => (
            <div key={scan.id} className="glass-card p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-cyan-500/10 rounded-xl flex items-center justify-center">
                    <FileText className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-white font-medium text-sm capitalize">
                      {scan.scan_type} Scan Report
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(scan.created_at).toLocaleDateString()}
                      </span>
                      <span>{scan.total_findings} findings</span>
                      <span className={`${
                        scan.exposure_score >= 50 ? 'text-red-400' :
                        scan.exposure_score >= 25 ? 'text-yellow-400' : 'text-green-400'
                      }`}>
                        Score: {scan.exposure_score?.toFixed(0)}/100
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Download buttons — links to MinIO/S3 URLs */}
                  {['pdf', 'json', 'csv'].map((fmt) => (
                    <a
                      key={fmt}
                      href={`/api/v1/scans/${scan.id}/report/${fmt}`}
                      className="text-xs px-3 py-1.5 border border-white/10 hover:border-cyan-500/40 text-gray-400 hover:text-cyan-400 rounded-lg transition-colors flex items-center gap-1"
                    >
                      <Download className="w-3 h-3" />
                      {fmt.toUpperCase()}
                    </a>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
