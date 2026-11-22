import MyParcels from '@/pages/MyParcels'
import Reports from '@/pages/Reports'
import Settings from '@/pages/Settings'
import Start from '@/pages/Start'
import { PageShell } from '@/layout/PageShell'
import { usePage } from '@/lib/router'

/**
 * Korzeń aplikacji: Start (mapa) albo jedna ze stron (SPEC 3). Adres: #dzialki, #raporty, #zgloszenia, #ustawienia.
 * Start czyta działkę/uprawę/datę z adresu, więc powrót na mapę odtwarza analizę.
 */
export default function App() {
  const page = usePage()
  // „Zgłoszenia” – ta sama mapa Startu z otwartym kreatorem zgłoszeń (rowy i zbiorniki)
  if (page === 'start' || page === 'infra') return <Start />
  return (
    <PageShell>
      {page === 'parcels' && <MyParcels />}
      {page === 'reports' && <Reports />}
      {page === 'settings' && <Settings />}
    </PageShell>
  )
}
