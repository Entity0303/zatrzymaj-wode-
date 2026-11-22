import type { ReactNode } from 'react'
import { BottomTabs } from './BottomTabs'
import { Sidebar } from './Sidebar'

/** Układ stron poza mapą (Moje działki, Raporty, Ustawienia): lewy pasek / dolne zakładki + przewijana treść. */
export function PageShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-bg">
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8 md:py-10">{children}</div>
        </main>
      </div>
      <BottomTabs />
    </div>
  )
}

/** Nagłówek strony: tytuł szeryfem + jedno zdanie wyjaśnienia + akcje po prawej. */
export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-[32px] leading-10 font-bold text-brand-dark">{title}</h1>
        <p className="mt-1 max-w-2xl text-base leading-6 text-text-muted">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  )
}
