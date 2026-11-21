import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Pusty stan: ilustracja + tytuł + instrukcja + akcja (SPEC 14). */
export function EmptyState({
  illustration,
  title,
  description,
  children,
  className,
}: {
  illustration?: ReactNode
  title: string
  description?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center text-center', className)}>
      {illustration}
      <h3 className="mt-3 text-lg leading-6 font-semibold">{title}</h3>
      {description && <p className="mt-1 text-sm leading-5 text-text-muted">{description}</p>}
      {children && <div className="mt-3 w-full">{children}</div>}
    </div>
  )
}
