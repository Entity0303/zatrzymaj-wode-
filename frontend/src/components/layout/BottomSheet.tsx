import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Snap = 'collapsed' | 'half' | 'full'

const ORDER: Snap[] = ['collapsed', 'half', 'full']
const LABEL: Record<Snap, string> = { collapsed: 'zwinięty', half: 'do połowy', full: 'pełny' }

/** Wysokości widocznej części szuflady dla danej wysokości obszaru mapy. */
export function snapHeights(h: number, collapsed: number, topReserved = 0): Record<Snap, number> {
  const full = h - topReserved
  return { collapsed, half: Math.min(full, Math.max(collapsed + 40, Math.round(h * 0.52))), full }
}

/**
 * Szuflada od dołu z trzema położeniami (SPEC 12, 14 BottomSheet):
 * zwinięta (nazwa działki + status + „Raport”), połowa (wskaźniki, „Co zrobić?”), pełna.
 * Przeciąganie za uchwyt/nagłówek, klik w uchwyt = następne położenie, Esc = zwiń.
 */
export function BottomSheet({
  areaHeight,
  collapsedHeight,
  topReserved = 0,
  snap,
  onSnapChange,
  header,
  children,
}: {
  areaHeight: number
  collapsedHeight: number
  /** wysokość górnego paska, którego szuflada nie zasłania */
  topReserved?: number
  snap: Snap
  onSnapChange: (s: Snap) => void
  header: ReactNode
  children: ReactNode
}) {
  const heights = snapHeights(areaHeight, collapsedHeight, topReserved)
  const [drag, setDrag] = useState<number | null>(null) // aktualna widoczna wysokość podczas przeciągania
  const start = useRef<{ y: number; h: number; moved: boolean } | null>(null)
  const visible = drag ?? heights[snap]

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onSnapChange('collapsed')
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onSnapChange])

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('button:not([data-sheet-handle]), a, [role=menuitem]')) return
    start.current = { y: e.clientY, h: heights[snap], moved: false }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!start.current) return
    const dy = start.current.y - e.clientY
    if (Math.abs(dy) > 6) start.current.moved = true
    if (start.current.moved) setDrag(Math.min(heights.full, Math.max(heights.collapsed - 30, start.current.h + dy)))
  }
  const onPointerUp = () => {
    const s = start.current
    start.current = null
    if (!s) return
    if (!s.moved) {
      setDrag(null)
      return
    }
    const h = drag ?? s.h
    const nearest = ORDER.reduce((best, k) => (Math.abs(heights[k] - h) < Math.abs(heights[best] - h) ? k : best), snap)
    setDrag(null)
    onSnapChange(nearest)
  }
  const next = () => onSnapChange(ORDER[(ORDER.indexOf(snap) + 1) % ORDER.length])

  return (
    <section
      aria-label="Panel działki"
      className={cn(
        'absolute inset-x-0 bottom-0 z-[1100] flex flex-col rounded-t-[20px] border-t bg-surface shadow-[0_-6px_24px_rgba(30,42,35,.16)]',
        drag === null && 'transition-transform duration-200 ease-out',
      )}
      style={{ height: heights.full, transform: `translateY(${heights.full - visible}px)` }}
    >
      <div
        className="shrink-0 touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <button
          type="button"
          data-sheet-handle
          onClick={next}
          aria-label={`Panel: ${LABEL[snap]}. Zmień położenie`}
          className="mx-auto flex h-6 w-full items-center justify-center"
        >
          <span className="h-1.5 w-11 rounded-full bg-nodata" />
        </button>
        <div className="px-4 pb-3">{header}</div>
      </div>
      <div className={cn('min-h-0 flex-1 overscroll-contain px-4 pb-6', snap === 'collapsed' ? 'overflow-hidden' : 'overflow-y-auto')}>
        {children}
      </div>
    </section>
  )
}
