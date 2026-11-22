import type { AnalysisResponse } from '@/api/types'
import { HydroCard } from '@/features/parcel-panel/HydroCard'
import { TerrainCard } from '@/features/parcel-panel/TerrainCard'
import { formatArea } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { PassportCard } from './PassportCard'

/**
 * 5a. Teren działki (F6): pasek stref (górka / stok / płasko / obniżenie) w % z legendą i zdaniem o każdej strefie,
 * opis terenu, dla dociekliwych – wysokości i spadki (TerrainCard bez własnej ramki); zdanie o kierunku spływu
 * i o wodzie, która dopływa spoza działki. Pod spodem rowy i zbiorniki w okolicy (500 m, wodowskaz).
 */
export function TerrainSection({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const ter = analysis.terrain && 'zones' in analysis.terrain ? analysis.terrain : null
  const inflowHa = ter?.inflow_from_outside_m2 ? ter.inflow_from_outside_m2 / 10_000 : 0
  const outlet = ter?.outlets?.[0]
  return (
    <div id="pp-teren" className="grid content-start gap-4">
      <h3 id="pp-teren-h" className="font-display text-[22px] leading-7 font-bold">
        {t('Teren i okolica')}
      </h3>
      <PassportCard title={t('Teren działki')}>
        <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} bare />
        {ter && (ter.main_flow_direction || inflowHa > 0.01 || outlet) && (
          <p className="mt-3 border-t border-paper-line pt-3 text-sm leading-5">
            {ter.main_flow_direction && <>{t('Po ulewie woda spływa głównie na {kier}.', { kier: t(ter.main_flow_direction) })} </>}
            {outlet && <>{t('Odpływa z działki na {kier} ({p}% działki).', { kier: t(outlet.direction), p: Math.round(outlet.share_of_parcel_pct) })} </>}
            {inflowHa > 0.01 && t('Woda dopływa też z ok. {a} spoza działki.', { a: formatArea(inflowHa) })}
          </p>
        )}
      </PassportCard>
      <PassportCard title={t('Rowy i zbiorniki')}>
        <HydroCard hydro={analysis.hydro} passport bare historicalDate={analysis.historical ? analysis.analysis_date : null} />
      </PassportCard>
    </div>
  )
}
