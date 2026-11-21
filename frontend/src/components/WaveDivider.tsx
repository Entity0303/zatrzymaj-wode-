import { cn } from '@/lib/utils'

/** Delikatny, organiczny podział sekcji – linia jak łagodne wzgórza (kolor szałwii). */
export function WaveDivider({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 12" preserveAspectRatio="none" className={cn('block h-3 w-full text-sage', className)} aria-hidden>
      <path
        d="M0 7c20-5 40-5 60 0s40 5 60 0 40-5 60 0 40 5 60 0 40-5 80 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity=".7"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
