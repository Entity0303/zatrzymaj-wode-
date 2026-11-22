import { createContext, useContext } from 'react'

/** F34: ukryta kopia paszportu do druku – jej sekcje dostają id z przyrostkiem, żeby id w dokumencie były unikalne. */
export const PassportPrintContext = createContext(false)

/** id sekcji paszportu: na ekranie bez zmian („pp-werdykt”), w kopii do druku „pp-werdykt-druk”. */
export function usePassportId(id: string): string {
  return useContext(PassportPrintContext) ? `${id}-druk` : id
}
