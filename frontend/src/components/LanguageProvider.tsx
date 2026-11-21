import { useState, type ReactNode } from 'react'
import { LangContext, applyLang, getLang, type Lang } from '@/lib/i18n'

/** Trzyma wybrany język (D30) i przerysowuje komponenty korzystające z useLang. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const l = getLang()
    applyLang(l)
    return l
  })
  const setLang = (l: Lang) => {
    applyLang(l)
    setLangState(l)
  }
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>
}
