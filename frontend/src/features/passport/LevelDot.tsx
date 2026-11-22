import type { VerdictStatementLevel } from '@/api/types'
import { cn } from '@/lib/utils'

/** Kolory poziomu (F6): ok – zielony ptaszek, warn – żółty „!”, bad – czerwony krzyżyk, info – niebieska kropla. */
const LEVEL: Record<VerdictStatementLevel, { cls: string; label: string }> = {
  ok: { cls: 'bg-pp-ok text-white', label: 'dobrze' },
  warn: { cls: 'bg-pp-warn text-text', label: 'uwaga' },
  bad: { cls: 'bg-pp-bad text-white', label: 'źle' },
  info: { cls: 'bg-pp-water text-white', label: 'informacja' },
}

/** Kółko poziomu z ikoną (inline SVG, bez emoji). */
export function LevelDot({ level, size = 22, className }: { level: VerdictStatementLevel; size?: number; className?: string }) {
  const l = LEVEL[level]
  return (
    <span
      role="img"
      aria-label={l.label}
      className={cn('inline-flex shrink-0 items-center justify-center rounded-full', l.cls, className)}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 16 16" width={size * 0.62} height={size * 0.62} aria-hidden fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        {level === 'ok' && <path d="M3.5 8.5l3 3 6-7" />}
        {level === 'warn' && (
          <>
            <path d="M8 3.5v5.5" />
            <path d="M8 12.5v.01" />
          </>
        )}
        {level === 'bad' && <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" />}
        {level === 'info' && <path d="M8 2.8c2.2 2.7 3.6 4.7 3.6 6.4a3.6 3.6 0 0 1-7.2 0c0-1.7 1.4-3.7 3.6-6.4z" fill="currentColor" stroke="none" />}
      </svg>
    </span>
  )
}
