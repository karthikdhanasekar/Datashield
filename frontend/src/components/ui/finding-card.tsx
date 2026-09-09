/**
 * FindingCard — reusable finding detail card
 */
'use client'

import { ExternalLink, Shield, XCircle } from 'lucide-react'
import { SeverityBadge } from './severity-badge'
import { truncate, getDomain } from '@/lib/utils'

interface FindingCardProps {
  finding: {
    id: string
    finding_type: string
    source_name?: string
    source_domain?: string
    source_url?: string
    severity: string
    risk_score: number
    description?: string
    exposed_data_types?: string[]
    credential_exposure?: boolean
    identity_theft_risk?: boolean
    financial_risk?: boolean
    government_id_exposure?: boolean
    snippet?: string
    is_false_positive?: boolean
    is_removed?: boolean
  }
  onRequestRemoval?: (id: string) => void
  onMarkFalsePositive?: (id: string) => void
  compact?: boolean
}

export function FindingCard({
  finding: f,
  onRequestRemoval,
  onMarkFalsePositive,
  compact = false,
}: FindingCardProps) {
  const domain = f.source_domain || (f.source_url ? getDomain(f.source_url) : 'Unknown')

  return (
    <div className={`glass-card p-4 hover:border-white/20 transition-colors ${
      f.is_removed ? 'opacity-50' : ''
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <SeverityBadge severity={f.severity} className="mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            {/* Source */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-white font-medium text-sm">{f.source_name || domain}</span>
              <span className="text-xs text-gray-500 bg-white/5 px-1.5 py-0.5 rounded">
                {f.finding_type.replace(/_/g, ' ')}
              </span>
              <span className="text-xs text-gray-600">
                Score: {f.risk_score.toFixed(1)}/10
              </span>
            </div>

            {/* Description */}
            {!compact && f.description && (
              <p className="text-gray-300 text-sm leading-relaxed mb-2">
                {truncate(f.description, 200)}
              </p>
            )}

            {/* Risk flags */}
            <div className="flex flex-wrap gap-1.5 mb-2">
              {f.credential_exposure && (
                <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">
                  🔑 Credentials
                </span>
              )}
              {f.identity_theft_risk && (
                <span className="text-[10px] text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded border border-orange-500/20">
                  🎭 ID Theft Risk
                </span>
              )}
              {f.financial_risk && (
                <span className="text-[10px] text-yellow-400 bg-yellow-500/10 px-1.5 py-0.5 rounded border border-yellow-500/20">
                  💳 Financial Risk
                </span>
              )}
              {f.government_id_exposure && (
                <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">
                  🪪 Gov ID Exposed
                </span>
              )}
            </div>

            {/* Exposed data types */}
            {f.exposed_data_types && f.exposed_data_types.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {f.exposed_data_types.slice(0, 5).map((dt) => (
                  <span key={dt} className="text-[10px] text-gray-400 bg-white/5 px-1.5 py-0.5 rounded">
                    {dt.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}

            {/* Snippet */}
            {!compact && f.snippet && (
              <div className="mt-2 p-2 bg-white/5 rounded text-xs text-gray-400 border border-white/5 line-clamp-2">
                {f.snippet}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1.5 flex-shrink-0">
          {f.source_url && (
            <a
              href={f.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-gray-500 hover:text-cyan-400 bg-white/5 rounded-lg transition-colors"
              title="View source"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
          {!f.is_removed && onRequestRemoval && (
            <button
              onClick={() => onRequestRemoval(f.id)}
              className="p-1.5 text-gray-500 hover:text-orange-400 bg-white/5 hover:bg-orange-500/10 rounded-lg transition-colors"
              title="Request removal"
            >
              <Shield className="w-3.5 h-3.5" />
            </button>
          )}
          {onMarkFalsePositive && (
            <button
              onClick={() => onMarkFalsePositive(f.id)}
              className="p-1.5 text-gray-500 hover:text-gray-300 bg-white/5 rounded-lg transition-colors"
              title="Mark false positive"
            >
              <XCircle className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
