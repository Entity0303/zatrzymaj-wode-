import { useId } from 'react'
import { cn } from '@/lib/utils'

/**
 * Słoneczne pole: niebo, słońce, łagodne wzgórza z szałwii i rzędy upraw zbiegające się w perspektywie,
 * kropla wody. Własny rysunek (pusty stan, karta hasła w lewym pasku) – zamiast zdjęć bez licencji.
 */
export function FieldIllustration({ className }: { className?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 160 96" className={cn('h-auto', className)} aria-hidden>
      <defs>
        <linearGradient id={`sky${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FCF0D8" />
          <stop offset="1" stopColor="#E8EFE2" />
        </linearGradient>
        <radialGradient id={`sun${id}`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#F6C66B" />
          <stop offset="0.6" stopColor="#E2A23B" stopOpacity=".55" />
          <stop offset="1" stopColor="#E2A23B" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="160" height="96" fill={`url(#sky${id})`} />
      <circle cx="124" cy="26" r="22" fill={`url(#sun${id})`} />
      <circle cx="124" cy="26" r="8" fill="#F2B54E" />
      <path d="M0 52c26-12 54-14 84-6s52 6 76-6v56H0z" fill="#9DB896" />
      <path d="M0 64c44-14 92-12 160-2v34H0z" fill="#5F9F63" />
      <path d="M0 74c50-8 104-8 160 0v22H0z" fill="#2E5B3F" />
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <path key={i} d={`M${-6 + i * 28} 96 L ${58 + i * 7} 66`} stroke="#B8D3A8" strokeWidth="1.6" opacity=".55" />
      ))}
      <path d="M30 26c3.6 4.4 5.6 7.6 5.6 10.2a5.6 5.6 0 0 1-11.2 0c0-2.6 2.1-5.8 5.6-10.2z" fill="#2F7FC1" />
      <path d="M27.6 37.6a3 3 0 0 0 2.4 2.2" stroke="#fff" strokeWidth="1.2" fill="none" strokeLinecap="round" opacity=".8" />
    </svg>
  )
}
