import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** F6: karta paszportu – biała, ramka #E4E0D6, zaokrąglenie 18 px, bez cienia. */
export function PassportCard({ children, className, title, aside }: { children: ReactNode; className?: string; title?: string; aside?: ReactNode }) {
  return (
    <div className={cn('min-w-0 rounded-[18px] border border-paper-line bg-surface p-5 md:p-6', className)}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          {title && <h4 className="text-base leading-6 font-bold">{title}</h4>}
          {aside}
        </div>
      )}
      {children}
    </div>
  )
}
