import { Sprout } from 'lucide-react'
import type { CropId } from '@/api/types'
import { Select, SelectContent, SelectItem, SelectSeparator, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CROPS, cropLabel } from '@/lib/crops'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

const NONE = '__bez_uprawy'

/**
 * 2. Uprawa – 15 upraw IUNG SMSR (SPEC 6.2). Od B3 uprawa jest opcjonalna (analiza działa bez niej):
 * `optional` – bez ostrzegawczego tła i podpowiedzi, z pozycją „Bez uprawy” do wyczyszczenia wyboru.
 */
export function CropField({
  crop,
  onChange,
  optional,
}: {
  crop: CropId | null
  onChange: (c: CropId | null) => void
  optional?: boolean
}) {
  const { t } = useLang()
  return (
    <div className="@container">
      <Select value={crop ?? ''} onValueChange={(v) => onChange(v === NONE ? null : (v as CropId))}>
        <SelectTrigger
          aria-label={t('Uprawa')}
          title={crop ? cropLabel(crop) ?? undefined : undefined}
          className={cn(
            'h-12 w-full rounded-md border bg-surface-2 px-3.5 text-base data-[size=default]:h-12 [&_svg:not([class*=size-])]:size-5',
            !crop && !optional && 'border-warn bg-warn-soft',
          )}
        >
          {/* wąskie pole: bez „Uprawa:” (ikona mówi, co to); za długa nazwa – „…”, strzałka zawsze widoczna */}
          <span className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <Sprout className="size-5 shrink-0 text-brand" aria-hidden />
            <span className="hidden shrink-0 text-text-muted @[340px]:inline">{t('Uprawa:')}</span>
            <span className="min-w-0 truncate text-left">
              <SelectValue placeholder={t(optional ? 'nie wybrano' : 'wybierz…')} />
            </span>
          </span>
        </SelectTrigger>
        <SelectContent className="z-[1500] max-h-80 rounded-xl" position="popper">
          {optional && crop && (
            <>
              <SelectItem value={NONE} className="min-h-11 text-base text-text-muted">
                {t('Bez uprawy (stan działki)')}
              </SelectItem>
              <SelectSeparator />
            </>
          )}
          {CROPS.map((c) => (
            <SelectItem key={c.id} value={c.id} className="min-h-11 text-base">
              {t(c.label)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!crop && !optional && <p className="mt-1.5 text-sm text-[#875a12]">{t('Wybierz, co rośnie na tej działce')}</p>}
    </div>
  )
}
