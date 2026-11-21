import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'

/**
 * Strona „Moje działki” – SZKIELET (nawigacja jeszcze nieaktywna).
 * TODO (osoba B): lista zapisanych działek (pamięć przeglądarki), status każdej, szybkie przejście do mapy (SPEC 3, 10).
 */
export default function MyParcels() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState illustration={<FieldIllustration className="w-40" />} title="Moje działki" description="W budowie." />
    </div>
  )
}
