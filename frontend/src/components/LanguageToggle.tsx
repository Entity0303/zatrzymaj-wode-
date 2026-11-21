import { Languages } from 'lucide-react'
import { useLang, type Lang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const LANGS: { id: Lang; label: string; name: string }[] = [
  { id: 'pl', label: 'PL', name: 'Polski' },
  { id: 'en', label: 'EN', name: 'English' },
]

/**
 * Przełącznik języka PL | EN (D40). Komputer: pigułka z dwoma przyciskami;
 * telefon (`compact`): jeden okrągły przycisk 48 px z kodem drugiego języka.
 * Nazwy języków celowo nie są tłumaczone – każdy widzi swój język po swojemu.
 */
export function LanguageToggle({ compact, bare, className }: { compact?: boolean; bare?: boolean; className?: string }) {
  const { lang, setLang, t } = useLang()
  if (compact) {
    const other = LANGS.find((l) => l.id !== lang)!
    return (
      <button
        type="button"
        onClick={() => setLang(other.id)}
        aria-label={`${t('Język')}: ${other.name}`}
        lang={other.id}
        className={cn(
          'flex size-12 shrink-0 items-center justify-center rounded-full bg-surface text-sm font-semibold text-brand shadow-float hover:bg-ok-soft',
          className,
        )}
      >
        {other.label}
      </button>
    )
  }
  return (
    <div
      role="radiogroup"
      aria-label={t('Język')}
      className={cn(
        'flex h-12 shrink-0 items-center gap-1 rounded-full bg-surface p-1 pl-3 shadow-float',
        bare && 'bg-transparent shadow-none',
        className,
      )}
    >
      <Languages className="size-5 shrink-0 text-brand" aria-hidden />
      {LANGS.map((l) => (
        <button
          key={l.id}
          type="button"
          role="radio"
          aria-checked={lang === l.id}
          aria-label={l.name}
          lang={l.id}
          onClick={() => setLang(l.id)}
          className={cn(
            'h-10 min-w-11 rounded-full px-2.5 text-sm font-semibold transition-colors',
            lang === l.id ? 'bg-brand text-white' : 'text-text-muted hover:bg-surface-2',
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  )
}
