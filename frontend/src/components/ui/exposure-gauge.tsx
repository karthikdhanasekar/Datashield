/**
 * ExposureGauge — SVG circular gauge for exposure score
 */
import { riskColor, riskLabel } from '@/lib/utils'

interface ExposureGaugeProps {
  score: number
  size?: number
}

export function ExposureGauge({ score, size = 160 }: ExposureGaugeProps) {
  const radius = (size / 2) - 14
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(score / 100, 1)
  const strokeDasharray = `${progress * circumference} ${circumference}`

  const strokeColor =
    score >= 80 ? '#ef4444' :
    score >= 50 ? '#f97316' :
    score >= 25 ? '#eab308' :
    '#22c55e'

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#1a3a73" strokeWidth="12"
        />
        {/* Progress */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={strokeColor} strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={strokeDasharray}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute text-center">
        <div className={`font-black ${riskColor(score)}`}
          style={{ fontSize: size * 0.22 }}>
          {Math.round(score)}
        </div>
        <div className="text-gray-500" style={{ fontSize: size * 0.09 }}>
          /100
        </div>
        <div className={`font-semibold ${riskColor(score)}`}
          style={{ fontSize: size * 0.1 }}>
          {riskLabel(score)}
        </div>
      </div>
    </div>
  )
}
