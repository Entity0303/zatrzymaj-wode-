import { useCallback, useState } from 'react'
import { ApiError, api, type AnalysisQuery, type ErrorInfo } from '@/api/client'

/** Błąd pobierania raportu po polsku – analiza na ekranie jest dalej dostępna. */
function describeReportError(e: unknown): ErrorInfo {
  const stillWorks = 'Wynik analizy na ekranie jest kompletny – możesz go też skopiować linkiem.'
  if (e instanceof ApiError && (e.status === 404 || e.status === 501))
    return { title: 'Raport PDF jest jeszcze w budowie', message: 'Serwer nie generuje jeszcze raportu.', stillWorks, retryable: false }
  if (e instanceof ApiError && e.status === 0)
    return { title: 'Brak połączenia', message: 'Nie można połączyć się z serwerem aplikacji. Sprawdź internet.', stillWorks, retryable: true }
  return { title: 'Nie udało się pobrać raportu', message: 'Spróbuj ponownie za chwilę.', stillWorks, retryable: true }
}

/**
 * „Pobierz raport PDF” – GET /api/report.pdf z tymi samymi parametrami co analiza.
 * Plik zapisywany przez przeglądarkę; błąd zwracany jako komunikat dla rolnika.
 */
export function useReportDownload(params: (AnalysisQuery & { numer: string }) | null) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ErrorInfo | null>(null)

  async function download(reportType: 'short' | 'full' = 'short') {
    if (!params || busy) return
    setBusy(true)
    setError(null)
    try {
      const blob = await api.reportPdf({ ...params, reportType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `raport-${reportType === 'full' ? 'szczegolowy' : 'skrocony'}-${params.numer.replace(/[^\w-]+/g, '_')}-${params.date}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (e) {
      setError(describeReportError(e))
    } finally {
      setBusy(false)
    }
  }

  const clearError = useCallback(() => setError(null), [])
  return { download, busy, error, clearError }
}
