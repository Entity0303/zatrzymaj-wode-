import { ArrowLeft, Camera, Check, Droplets, FileDown, Loader2, MapPin, MousePointerClick, Save, X } from 'lucide-react'
import { useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { Hydro, HydroFeature, InfraProblem, InfraReportIn, Parcel, WaterLevel, WaterObjectType } from '@/api/types'
import { formatDistance, HYDRO_KIND } from '@/lib/hydro'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'
import { LEVEL, OBJECT, PROBLEM, TONE_HEX } from './infra'
import { buildLetter } from './letter'

const STEPS = ['Obiekt', 'Problem', 'Zdjęcie', 'Podsumowanie'] as const

type SaveState = { phase: 'idle' | 'saving' | 'saved' | 'unavailable' | 'error' }

/** rodzaj wody z hydro → rodzaj obiektu zgłoszenia */
const TO_OBJECT: Record<HydroFeature['kind'], WaterObjectType> = { row: 'row', ciek: 'ciek', rzeka: 'ciek', kanal: 'ciek', zbiornik: 'zbiornik' }

/**
 * Zgłoszenie stanu rowu / cieku / zbiornika (SPEC 11): 1. obiekt i miejsce na mapie · 2. problem i poziom wody ·
 * 3. zdjęcie (opcjonalnie, zostaje na urządzeniu) i opis · 4. adresat, „Pobierz gotowe pismo”, zapis na mapie.
 * „Nic nie wysyłamy automatycznie.”
 */
export function InfraReportWizard({
  parcel,
  point,
  onPickPoint,
  onClose,
  onSaved,
  hydro,
}: {
  /** F3: woda w okolicy – podpowiedź najbliższego rowu */
  hydro?: Hydro | null
  parcel: Parcel | null
  /** wskazane miejsce [lon, lat] (domyślnie środek działki) */
  point: [number, number] | null
  /** przełącza mapę w tryb wskazywania miejsca */
  onPickPoint: () => void
  onClose: () => void
  onSaved?: () => void
}) {
  const { t } = useLang()
  const [step, setStep] = useState(0)
  // F3: najbliższy rów z wody w okolicy (a bez rowów – najbliższy obiekt); obiekty nie mają położenia – tylko podpowiedź
  const feats = hydro?.status === 'ok' ? (hydro.features ?? []) : []
  const byDist = [...feats].sort((a, b) => a.distance_m - b.distance_m)
  const nearest = byDist.find((f) => f.kind === 'row') ?? byDist[0] ?? null
  const [type, setType] = useState<WaterObjectType | null>(null)
  const [problem, setProblem] = useState<InfraProblem | null>(null)
  const [level, setLevel] = useState<WaterLevel | null>(null)
  const [description, setDescription] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [save, setSave] = useState<SaveState>({ phase: 'idle' })

  const canNext = step === 0 ? !!type && !!point : step === 1 ? !!problem : true
  const report: InfraReportIn | null =
    type && problem && point
      ? { object_type: type, lon: point[0], lat: point[1], problem, water_level: level, description: description.trim() || null }
      : null

  function downloadLetter() {
    if (!report) return
    const blob = new Blob([buildLetter(report, parcel, !!photo)], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `zgloszenie-${report.object_type}-${new Date().toISOString().slice(0, 10)}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  }

  async function saveOnMap() {
    if (!report) return
    setSave({ phase: 'saving' })
    try {
      await api.createInfraReport(report)
      setSave({ phase: 'saved' })
      onSaved?.()
    } catch (e) {
      setSave({ phase: e instanceof ApiError && (e.status === 404 || e.status === 501) ? 'unavailable' : 'error' })
    }
  }

  const tile = (active: boolean) =>
    cn(
      'flex min-h-14 items-center gap-3 rounded-xl border p-3 text-left text-base font-medium transition-colors',
      active ? 'border-brand bg-sage-soft text-brand-dark' : 'bg-surface hover:bg-surface-2',
    )

  return (
    <section aria-label={t('Zgłoś stan wody w okolicy')} className="flex max-h-full flex-col">
      <header className="space-y-3 border-b px-5 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display min-w-0 flex-1 text-xl leading-7 font-semibold">{t('Zgłoś stan rowu lub zbiornika')}</h2>
          <button type="button" onClick={onClose} aria-label={t('Zamknij')} className="flex size-11 items-center justify-center rounded-full hover:bg-surface-2">
            <X className="size-5" />
          </button>
        </div>
        <ol className="grid grid-cols-4 gap-1.5" aria-label={t('Kroki zgłoszenia')}>
          {STEPS.map((s, i) => (
            <li key={s} className="space-y-1">
              <span className={cn('block h-1.5 rounded-full', i <= step ? 'bg-brand' : 'bg-surface-2')} />
              <span className={cn('block text-xs leading-4', i === step ? 'font-semibold text-brand-dark' : 'text-text-muted')}>
                {i + 1}. {t(s)}
              </span>
            </li>
          ))}
        </ol>
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {step === 0 && (
          <>
            {nearest && (
              <div className="flex items-start gap-2.5 rounded-xl bg-water-soft/70 p-3 text-sm leading-5">
                <Droplets className="mt-0.5 size-4 shrink-0 text-water" aria-hidden />
                <span className="min-w-0 flex-1">
                  {t('Najbliżej działki:')} <b>{t(HYDRO_KIND[nearest.kind])}</b>
                  {nearest.name && ` ${nearest.name}`} · {formatDistance(nearest.distance_m)}
                  {nearest.toward_outflow && <span className="block text-xs leading-4 text-text-muted">{t('w stronę, w którą woda spływa z działki')}</span>}
                </span>
                <button
                  type="button"
                  onClick={() => setType(TO_OBJECT[nearest.kind])}
                  className="h-9 shrink-0 rounded-md border bg-surface px-3 text-sm font-medium hover:bg-surface-2"
                >
                  {t('Zgłoś ten')}
                </button>
              </div>
            )}
            <p className="text-sm leading-5 text-text-muted">{t('Czego dotyczy zgłoszenie?')}</p>
            <div role="radiogroup" aria-label={t('Rodzaj obiektu')} className="grid gap-2">
              {(Object.keys(OBJECT) as WaterObjectType[]).map((k) => (
                <button key={k} type="button" role="radio" aria-checked={type === k} onClick={() => setType(k)} className={tile(type === k)}>
                  {type === k ? <Check className="size-5 text-brand" /> : <span className="size-5 rounded-full border-2" />}
                  {t(OBJECT[k].label)}
                </button>
              ))}
            </div>
            <div className="space-y-2 rounded-xl bg-surface-2/60 p-3">
              <p className="flex items-center gap-2 text-sm leading-5 font-medium">
                <MapPin className="size-4 text-amber" />
                {point ? t('Miejsce: {lat}, {lon}', { lat: point[1].toFixed(5), lon: point[0].toFixed(5) }) : t('Nie wskazano miejsca')}
              </p>
              <button
                type="button"
                onClick={onPickPoint}
                className="flex h-11 items-center gap-2 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2"
              >
                <MousePointerClick className="size-4 text-brand" /> {t(point ? 'Wskaż inne miejsce na mapie' : 'Wskaż miejsce na mapie')}
              </button>
              {parcel && <p className="text-xs leading-4 text-text-muted">{t('Domyślnie: środek wybranej działki.')}</p>}
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <p className="text-sm leading-5 text-text-muted">{t('Jaki jest stan?')}</p>
            <div role="radiogroup" aria-label={t('Stan obiektu')} className="grid gap-2 sm:grid-cols-2">
              {(Object.keys(PROBLEM) as InfraProblem[]).map((k) => (
                <button key={k} type="button" role="radio" aria-checked={problem === k} onClick={() => setProblem(k)} className={tile(problem === k)}>
                  <span className="size-3.5 shrink-0 rounded-full" style={{ background: TONE_HEX[PROBLEM[k].tone] }} aria-hidden />
                  {t(PROBLEM[k].label)}
                </button>
              ))}
            </div>
            <p className="pt-1 text-sm leading-5 text-text-muted">{t('Poziom wody (opcjonalnie)')}</p>
            <div role="radiogroup" aria-label={t('Poziom wody')} className="flex flex-wrap gap-2">
              {(Object.keys(LEVEL) as WaterLevel[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={level === k}
                  onClick={() => setLevel(level === k ? null : k)}
                  className={cn(
                    'h-11 rounded-full border px-4 text-sm font-medium',
                    level === k ? 'border-brand bg-sage-soft text-brand-dark' : 'bg-surface hover:bg-surface-2',
                  )}
                >
                  {t(LEVEL[k])}
                </button>
              ))}
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed bg-surface-2/40 p-4 text-center hover:bg-surface-2">
              {photo ? (
                <img src={photo} alt={t('Zdjęcie obiektu')} className="max-h-48 rounded-lg object-contain" />
              ) : (
                <>
                  <Camera className="size-7 text-brand" aria-hidden />
                  <span className="text-base font-medium">{t('Dodaj zdjęcie (opcjonalnie)')}</span>
                </>
              )}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  const r = new FileReader()
                  r.onload = () => setPhoto(String(r.result))
                  r.readAsDataURL(f)
                }}
              />
            </label>
            <p className="text-xs leading-4 text-text-muted">{t('Zdjęcie zostaje na Twoim urządzeniu – dołącz je do pisma.')}</p>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">{t('Krótki opis (opcjonalnie)')}</span>
              <textarea
                id="infra-description"
                value={description}
                onChange={(e) => setDescription(e.target.value.slice(0, 500))}
                rows={3}
                placeholder={t('Np. przepust pod drogą zatkany gałęziami, woda stoi na polu.')}
                className="w-full rounded-md border bg-surface p-3 text-base outline-none focus-visible:border-brand"
              />
            </label>
          </>
        )}

        {step === 3 && report && (
          <>
            <dl className="space-y-2 rounded-xl bg-surface-2/60 p-4 text-sm leading-5">
              <div className="flex justify-between gap-3">
                <dt className="text-text-muted">{t('Obiekt')}</dt>
                <dd className="text-right font-medium">{t(OBJECT[report.object_type].label)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-text-muted">{t('Stan')}</dt>
                <dd className="text-right font-medium">{t(PROBLEM[report.problem].label)}</dd>
              </div>
              {report.water_level && (
                <div className="flex justify-between gap-3">
                  <dt className="text-text-muted">{t('Poziom wody')}</dt>
                  <dd className="text-right font-medium">{t(LEVEL[report.water_level])}</dd>
                </div>
              )}
              <div className="flex justify-between gap-3">
                <dt className="text-text-muted">{t('Miejsce')}</dt>
                <dd className="tabular text-right font-medium">
                  {report.lat.toFixed(5)}, {report.lon.toFixed(5)}
                </dd>
              </div>
            </dl>
            <div className="rounded-xl border border-sage bg-sage-soft p-4">
              <p className="text-sm leading-5 text-text-muted">{t('Do kogo skierować pismo')}</p>
              <p className="font-display text-lg leading-6 font-semibold">{t(OBJECT[report.object_type].addressee)}</p>
              <p className="mt-1 text-sm leading-5">{t(OBJECT[report.object_type].hint)}</p>
            </div>
            <button
              type="button"
              onClick={downloadLetter}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-md bg-brand-dark text-base font-semibold text-white hover:bg-brand"
            >
              <FileDown className="size-5" /> {t('Pobierz gotowe pismo')}
            </button>
            <button
              type="button"
              onClick={saveOnMap}
              disabled={save.phase === 'saving' || save.phase === 'saved'}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-md border bg-surface text-sm font-medium hover:bg-surface-2 disabled:opacity-70"
            >
              {save.phase === 'saving' ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4 text-brand" />}
              {t(save.phase === 'saved' ? 'Zapisano na mapie' : 'Pokaż zgłoszenie innym rolnikom na mapie')}
            </button>
            {save.phase === 'unavailable' && (
              <p role="status" className="rounded-md bg-amber-soft px-3 py-2 text-sm leading-5">
                {t('Zapisywanie zgłoszeń na mapie jest chwilowo niedostępne. Pismo możesz pobrać już teraz.')}
              </p>
            )}
            {save.phase === 'error' && (
              <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm leading-5 text-danger">
                {t('Nie udało się zapisać zgłoszenia. Pismo możesz pobrać – działa bez internetu.')}
              </p>
            )}
            <p className="text-center text-sm font-medium text-text-muted">{t('Nic nie wysyłamy automatycznie.')}</p>
          </>
        )}
      </div>

      <footer className="flex gap-2 border-t px-5 py-3">
        {step > 0 && (
          <button
            type="button"
            onClick={() => setStep(step - 1)}
            className="flex h-11 items-center gap-1.5 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2"
          >
            <ArrowLeft className="size-4" /> {t('Wstecz')}
          </button>
        )}
        {step < STEPS.length - 1 && (
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            disabled={!canNext}
            className="ml-auto h-11 rounded-md bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {t(step === 2 ? 'Dalej – podsumowanie' : 'Dalej')}
          </button>
        )}
      </footer>
    </section>
  )
}
