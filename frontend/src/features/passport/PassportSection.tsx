import type { ReactNode } from 'react'
import { usePassportId } from './passportId'

/**
 * Sekcja paszportu (F6): pogrubiony nagłówek, `id` = kotwica zakładki (scroll-margin-top ustawia Passport),
 * `aside` – element po prawej stronie nagłówka (np. przycisk).
 */
export function PassportSection({ id: baseId, title, aside, children }: { id: string; letter?: string; title: string; aside?: ReactNode; children: ReactNode }) {
  const id = usePassportId(baseId)
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="space-y-4 break-inside-avoid-page">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`${id}-h`} className="font-display text-[22px] leading-7 font-bold text-text">
          {title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  )
}
