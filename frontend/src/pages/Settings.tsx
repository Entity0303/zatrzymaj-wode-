import { Check, Map as MapIcon, Satellite, Sprout, Trash2, UserRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { PageHeader } from '@/layout/PageShell'
import { useLang } from '@/lib/i18n'
import { HISTORY_KEY, SAVED_KEY, SETTINGS_KEY, useSettings, writeStored, type Settings as S } from '@/lib/storage'
import { cn } from '@/lib/utils'

function Card({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="space-y-4 rounded-xl bg-surface p-5 shadow-card md:p-6">
      <div>
        <h2 className="font-display text-xl leading-7 font-semibold">{title}</h2>
        <p className="text-sm leading-5 text-text-muted">{description}</p>
      </div>
      {children}
    </section>
  )
}

function Choice({ active, onClick, icon, title, text }: { active: boolean; onClick: () => void; icon: ReactNode; title: string; text: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={cn(
        'flex min-h-11 flex-1 items-start gap-3 rounded-xl border p-4 text-left transition-colors',
        active ? 'border-brand bg-sage-soft' : 'bg-surface hover:bg-surface-2',
      )}
    >
      <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', active ? 'bg-brand text-white' : 'bg-surface-2 text-text-muted')}>
        {active ? <Check className="size-5" /> : icon}
      </span>
      <span>
        <span className="block text-base leading-6 font-semibold">{title}</span>
        <span className="block text-sm leading-5 text-text-muted">{text}</span>
      </span>
    </button>
  )
}

/** „Ustawienia” (SPEC 3): podkład mapy, tryb rolnik / doradca, język, wyczyszczenie zapisanych danych. */
export default function Settings() {
  const { t } = useLang()
  const [settings, setSettings] = useSettings()
  const [cleared, setCleared] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const set = (patch: Partial<S>) => setSettings({ ...settings, ...patch })

  const clear = (key: string, label: string) => {
    writeStored(key, undefined)
    setConfirm(null)
    setCleared(label)
  }

  return (
    <>
      <PageHeader title={t('Ustawienia')} description={t('Zapisują się tylko w tej przeglądarce. Nie mamy kont ani haseł.')} />
      <div className="space-y-5">
        <Card title={t('Podkład mapy')} description={t('Co widać pod działką po otwarciu mapy.')}>
          <div role="radiogroup" aria-label={t('Podkład mapy')} className="flex flex-col gap-3 sm:flex-row">
            <Choice
              active={settings.baseMap === 'orto'}
              onClick={() => set({ baseMap: 'orto' })}
              icon={<Satellite className="size-5" />}
              title={t('Zdjęcie z lotu ptaka')}
              text={t('Ortofotomapa GUGiK – widać pola, drzewa i rowy.')}
            />
            <Choice
              active={settings.baseMap === 'osm'}
              onClick={() => set({ baseMap: 'osm' })}
              icon={<MapIcon className="size-5" />}
              title={t('Zwykła mapa')}
              text={t('OpenStreetMap – drogi i nazwy miejscowości.')}
            />
          </div>
        </Card>

        <Card title={t('Tryb')} description={t('Doradca widzi od razu więcej liczb i uzasadnień.')}>
          <div role="radiogroup" aria-label={t('Tryb')} className="flex flex-col gap-3 sm:flex-row">
            <Choice
              active={settings.mode === 'rolnik'}
              onClick={() => set({ mode: 'rolnik' })}
              icon={<Sprout className="size-5" />}
              title={t('Rolnik')}
              text={t('Najpierw krótki wynik i zalecenia, szczegóły po kliknięciu.')}
            />
            <Choice
              active={settings.mode === 'doradca'}
              onClick={() => set({ mode: 'doradca' })}
              icon={<UserRound className="size-5" />}
              title={t('Doradca')}
              text={t('Uzasadnienia zaleceń i postęp analizy rozwinięte od razu.')}
            />
          </div>
        </Card>

        <Card title={t('Zapisane dane')} description={t('Usuń to, co ta przeglądarka pamięta. Tego nie da się cofnąć.')}>
          <div className="flex flex-wrap gap-2">
            {(
              [
                [SAVED_KEY, 'Moje działki'],
                [HISTORY_KEY, 'Historia raportów'],
                [SETTINGS_KEY, 'Ustawienia'],
              ] as const
            ).map(([key, label]) =>
              confirm === key ? (
                <button key={key} type="button" onClick={() => clear(key, label)} className="h-11 rounded-md bg-danger px-4 text-sm font-semibold text-white">
                  {t('Na pewno usuń: {what}', { what: t(label) })}
                </button>
              ) : (
                <button
                  key={key}
                  type="button"
                  onClick={() => setConfirm(key)}
                  className="flex h-11 items-center gap-2 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2"
                >
                  <Trash2 className="size-4 text-danger" /> {t('Usuń: {what}', { what: t(label) })}
                </button>
              ),
            )}
          </div>
          {cleared && (
            <p role="status" className="text-sm text-brand">
              {t('Usunięto: {what}', { what: t(cleared) })}
            </p>
          )}
        </Card>
      </div>
    </>
  )
}
