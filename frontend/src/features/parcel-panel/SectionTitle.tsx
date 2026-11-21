import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function SectionTitle({ children, icon: Icon }: { children: ReactNode; icon?: LucideIcon }) {
  return (
    <h3 className="font-display flex items-center gap-2 text-xl leading-7 font-semibold text-brand-dark">
      {Icon && <Icon className="size-5 text-brand" aria-hidden />}
      {children}
    </h3>
  )
}
