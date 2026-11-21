import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'

/**
 * Strona „Raporty” – SZKIELET (nawigacja jeszcze nieaktywna).
 * TODO (osoba B): poprzednie paszporty wodne, PDF, druk, link do udostępnienia (SPEC 10.1).
 */
export default function Reports() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState illustration={<FieldIllustration className="w-40" />} title="Raporty" description="W budowie." />
    </div>
  )
}
