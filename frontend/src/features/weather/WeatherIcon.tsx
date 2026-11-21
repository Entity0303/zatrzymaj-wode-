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
import type { WeatherIcon as WeatherIconKey } from '@/api/types'
import { cn } from '@/lib/utils'

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
