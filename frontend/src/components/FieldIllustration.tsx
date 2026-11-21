import { cn } from '@/lib/utils'

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
