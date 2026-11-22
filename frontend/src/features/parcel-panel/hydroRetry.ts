import { createContext, useContext } from 'react'

/**
 * F6: stan „woda w okolicy nie przyszła” (502 / limit czasu Overpass) i ponowienie samego /api/hydro –
 * dla karty „Woda w okolicy” w panelu, szczegółach i paszporcie (bez przekazywania przez wszystkie poziomy).
 */
export type HydroRetry = { failed: boolean; retry?: () => void }

export const HydroRetryContext = createContext<HydroRetry>({ failed: false })

export const useHydroRetry = () => useContext(HydroRetryContext)
