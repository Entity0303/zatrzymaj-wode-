import { createContext, useContext } from 'react'
import { EN } from './i18n.en'

/**
 * Język interfejsu (D35): domyślnie polski, opcjonalnie angielski.
 * Kluczem tłumaczenia jest SAM TEKST POLSKI – kod pozostaje czytelny po polsku:
 *   t('Szukam działki') · t('Znaleziono {n} działek', { n: 3 })
 * Brak wpisu w słowniku EN = tekst polski (bezpieczny zapas, np. teksty z backendu).
 */
export type Lang = 'pl' | 'en'

const KEY = 'zw.lang.v1'

function load(): Lang {
  try {
    return localStorage.getItem(KEY) === 'en' ? 'en' : 'pl'
  } catch {
    return 'pl'
  }
}

let current: Lang = load()

export const getLang = () => current

/** Ustawia język globalnie (używa go LanguageProvider – komponenty zmieniają język przez useLang). */
export function applyLang(lang: Lang) {
  current = lang
  document.documentElement.lang = lang
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    /* tryb prywatny – język tylko do odświeżenia strony */
  }
}

/** Locale do liczb i dat: 5,01 (pl) / 5.01 (en). */
export const locale = () => (current === 'en' ? 'en-GB' : 'pl-PL')

type Vars = Record<string, string | number>

const missing = new Set<string>()

/** Tłumaczy polski tekst na bieżący język i podstawia {zmienne}. */
export function tr(pl: string, vars?: Vars): string {
  let s = pl
  if (current === 'en') {
    const en = EN[pl]
    if (en !== undefined) s = en
    else if (import.meta.env.DEV && pl.trim() && !missing.has(pl)) {
      missing.add(pl)
      console.warn('[i18n] brak tłumaczenia EN:', pl)
    }
  }
  return vars ? s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m)) : s
}

export const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: current,
  setLang: () => undefined,
})

/** Język + funkcja t(); komponent używający useLang przerysuje się po zmianie języka. */
export function useLang() {
  const { lang, setLang } = useContext(LangContext)
  return { lang, setLang, t: tr }
}
