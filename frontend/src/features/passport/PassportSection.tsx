import type { ReactNode } from 'react'

/** Nagłówek sekcji paszportu: litera A–E w kółku + tytuł szeryfem; `id` = kotwica dla nawigacji. */
export function PassportSection({ id, letter, title, children }: { id: string; letter: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-16 space-y-4 break-inside-avoid-page">
      <h3 id={`${id}-h`} className="font-display flex items-center gap-2.5 text-[22px] leading-7 font-semibold text-brand-dark">
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sage-soft font-sans text-sm font-bold text-brand"
          aria-hidden
        >
          {letter}
        </span>
        {title}
      </h3>
      {children}
    </section>
  )
}
