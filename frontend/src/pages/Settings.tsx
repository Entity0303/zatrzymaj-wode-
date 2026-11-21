import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'

/**
 * Strona „Ustawienia” – SZKIELET (nawigacja jeszcze nieaktywna).
 * TODO (osoba B): podkład mapy, jednostki, tryb rolnik / doradca, wyczyszczenie zapisanych danych (SPEC 3).
 */
export default function Settings() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState illustration={<FieldIllustration className="w-40" />} title="Ustawienia" description="W budowie." />
    </div>
  )
}
