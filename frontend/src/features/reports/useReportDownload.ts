import { useCallback, useRef, useState } from 'react'
import { ApiError, api, type AnalysisQuery, type ErrorInfo } from '@/api/client'
import { addMyPdfReport } from './myReports'

export type ReportType = 'short' | 'full'

/** F25: limit czasu generowania raportu – potem komunikat i „Spróbuj ponownie”. */
const REPORT_TIMEOUT_MS = 60_000

/** Błąd pobierania raportu po polsku – analiza na ekranie jest dalej dostępna. */
function describeReportError(e: unknown, timedOut: boolean): ErrorInfo {
  const stillWorks = 'Wynik analizy na ekranie jest kompletny – możesz go też skopiować linkiem.'
  if (timedOut)
    return { title: 'Raport generuje się dłużej niż minutę', message: 'Serwer nie zdążył przygotować raportu. Spróbuj ponownie – drugi raz jest zwykle szybciej.', stillWorks, retryable: true }
  if (e instanceof ApiError && (e.status === 404 || e.status === 501))
    return { title: 'Nie udało się przygotować raportu PDF', message: 'Coś poszło nie tak. Spróbuj jeszcze raz.', stillWorks, retryable: true }
  if (e instanceof ApiError && e.status === 0)
    return { title: 'Brak połączenia', message: 'Nie można połączyć się z serwerem aplikacji. Sprawdź internet.', stillWorks, retryable: true }
  return { title: 'Nie udało się pobrać raportu', message: 'Spróbuj ponownie za chwilę.', stillWorks, retryable: true }
}

/**
 * „Pobierz raport PDF” – GET /api/report.pdf z tymi samymi parametrami co analiza (uprawa, okres, data siewu).
 * Plik zapisywany przez przeglądarkę; błąd zwracany jako komunikat dla rolnika. F25: `busyType` – który rodzaj się
 * generuje (stan na klikniętym przycisku), limit 60 s, `retry` – ten sam rodzaj jeszcze raz; udany raport działki
 * trafia na listę „Moje raporty” (same parametry, bez pliku).
 */
export function useReportDownload(params: (AnalysisQuery & { numer: string; obreb?: string | null; gmina?: string | null }) | null) {
  const [busyType, setBusyType] = useState<ReportType | null>(null)
  const [error, setError] = useState<ErrorInfo | null>(null)
  const last = useRef<ReportType>('short')

  async function download(reportType: ReportType = 'short') {
    if (!params || busyType) return
    last.current = reportType
    setBusyType(reportType)
    setError(null)
    const ctrl = new AbortController()
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      ctrl.abort()
    }, REPORT_TIMEOUT_MS)
    try {
      const { numer, obreb, gmina, ...query } = params
      const blob = await api.reportPdf({ ...query, reportType }, ctrl.signal)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `raport-${reportType === 'full' ? 'szczegolowy' : 'skrocony'}-${numer.replace(/[^\w-]+/g, '_')}-${params.date}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
      // „Moje raporty”: tylko działka ewidencyjna (obrysu narysowanego pola nie zapamiętujemy)
      if (query.parcelId && !query.geometry && !query.point)
        addMyPdfReport({
          params: {
            parcelId: query.parcelId,
            crop: query.crop ?? null,
            date: query.date,
            cropHistory: query.cropHistory,
            area: query.area ?? null,
            plannedCrops: query.plannedCrops,
            period: query.period ?? null,
            sowingDate: query.sowingDate ?? null,
          },
          type: reportType,
          numer,
          obreb: obreb ?? null,
          gmina: gmina ?? null,
        })
    } catch (e) {
      setError(describeReportError(e, timedOut))
    } finally {
      clearTimeout(timer)
      setBusyType(null)
    }
  }

  const clearError = useCallback(() => setError(null), [])
  return { download, retry: () => download(last.current), busy: busyType !== null, busyType, error, clearError }
}
