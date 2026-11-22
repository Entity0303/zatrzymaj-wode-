import { useEffect, useState } from 'react'
import { writeLink, type LinkState } from './deepLink'

/**
 * Strony aplikacji (SPEC 3) – w adresie jako #dzialki, #raporty, #zgloszenia, #ustawienia; Start = bez #.
 * „Zgłoszenia” (rowy i zbiorniki) to widok mapy Startu z otwartym kreatorem zgłoszeń.
 */
export type PageKey = 'start' | 'parcels' | 'reports' | 'infra' | 'settings'

const HASH: Record<PageKey, string> = { start: '', parcels: 'dzialki', reports: 'raporty', infra: 'zgloszenia', settings: 'ustawienia' }

function pageFromHash(): PageKey {
  const h = window.location.hash.replace(/^#/, '')
  return (Object.keys(HASH) as PageKey[]).find((k) => HASH[k] === h && h) ?? 'start'
}

export function usePage(): PageKey {
  const [page, setPage] = useState(pageFromHash)
  useEffect(() => {
    const on = () => setPage(pageFromHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return page
}

/**
 * Przejście do strony; dla Startu można od razu podać działkę/uprawę/datę (link do analizy).
 * Start czyta je z adresu przy wejściu.
 */
export function goTo(page: PageKey, link?: Partial<LinkState>) {
  if (link) writeLink(link)
  const hash = HASH[page]
  const url = new URL(window.location.href)
  url.hash = hash
  if (url.href !== window.location.href) {
    window.history.pushState(null, '', hash ? url : url.href.replace(/#$/, ''))
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
}
