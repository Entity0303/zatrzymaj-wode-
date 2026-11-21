import type { ReactNode } from 'react'

/** Nagłówek sekcji paszportu (bez liter A–E – zakładki u góry mają same nazwy); `id` = kotwica zakładki. */
export function PassportSection({ id, title, children }: { id: string; letter?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="space-y-4 break-inside-avoid-page">
      <h3 id={`${id}-h`} className="font-display text-[22px] leading-7 font-semibold text-brand-dark">
        {title}
      </h3>
      {children}
    </section>
  )
}
