import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  HelpCircle,
  Moon,
  Sun,
} from 'lucide-react'
import type { WeatherIcon as WeatherIconKey } from '@/api'
import { cn } from '@/lib/utils'

/** Znak marki: kropla w liściu (SPEC 4.1). Własny rysunek. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <rect width="40" height="40" rx="12" fill="#2F6B47" />
      {/* liść */}
      <path d="M10 29c0-11 8-18 20-19-1 12-8 20-19 20" fill="#5BB37F" />
      <path d="M11 29c5-6 10-10 16-15" stroke="#1F4D33" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      {/* kropla */}
      <path d="M21 15.5c2.4 3 3.8 5.2 3.8 7a3.8 3.8 0 0 1-7.6 0c0-1.8 1.4-4 3.8-7z" fill="#E3F0FB" stroke="#2F80C9" strokeWidth="1.2" />
    </svg>
  )
}

/** Ilustracja pola z rzędami upraw i kroplą (pusty stan, karta w lewym pasku). Własny rysunek. */
export function FieldIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 96" className={cn('h-auto', className)} aria-hidden>
      <rect width="160" height="96" rx="14" fill="#E6F4EA" />
      <circle cx="128" cy="22" r="10" fill="#FDF4D8" />
      <path d="M0 50c30-14 60-16 90-8s50 6 70-4v58H0z" fill="#5BB37F" />
      <path d="M0 62c40-12 80-12 160-2v36H0z" fill="#2F6B47" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <path
          key={i}
          d={`M${14 + i * 24} 96 Q ${40 + i * 18} 72 ${60 + i * 14} 62`}
          stroke="#8FCB9F"
          strokeWidth="2"
          fill="none"
          opacity=".7"
        />
      ))}
      <path d="M34 30c3.5 4.4 5.6 7.6 5.6 10.2a5.6 5.6 0 0 1-11.2 0c0-2.6 2.1-5.8 5.6-10.2z" fill="#2F80C9" />
    </svg>
  )
}

const WEATHER = {
  sun: Sun,
  'cloud-sun': CloudSun,
  cloud: Cloud,
  fog: CloudFog,
  drizzle: CloudDrizzle,
  rain: CloudRain,
  snow: CloudSnow,
  storm: CloudLightning,
  unknown: HelpCircle,
} as const

export function WeatherIcon({ icon, night, className }: { icon: WeatherIconKey; night?: boolean; className?: string }) {
  const Icon = night && icon === 'sun' ? Moon : (WEATHER[icon] ?? HelpCircle)
  const color =
    icon === 'sun' || icon === 'cloud-sun' ? 'text-warn' : icon === 'rain' || icon === 'drizzle' || icon === 'storm' ? 'text-water' : 'text-text-muted'
  return <Icon className={cn(color, className)} aria-hidden />
}
