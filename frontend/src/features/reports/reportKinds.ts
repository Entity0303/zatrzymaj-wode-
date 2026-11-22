import { FileDown, FileText, type LucideIcon } from 'lucide-react'
import type { ReportType } from './useReportDownload'

/** Rodzaje raportu PDF – tytuł i jednolinijkowy opis (panel, zakładka „Raporty”, menu w paszporcie). */
export const REPORT_KINDS: { type: ReportType; title: string; description: string; icon: LucideIcon }[] = [
  { type: 'short', title: 'Wygeneruj i pobierz raport skrócony', description: 'PDF, 2 strony: werdykt, wykresy, co posiać, co zrobić', icon: FileDown },
  { type: 'full', title: 'Wygeneruj i pobierz raport pełny', description: 'PDF, szczegółowy: wszystkie dane, źródła i ograniczenia', icon: FileText },
]
