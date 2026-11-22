import type L from 'leaflet'

/** Atrybut znacznika obrazu gleby w panelu SVG Leafletu – sprzątanie osieroconych elementów. */
export const SOIL_ATTR = 'data-soil-overlay'

/**
 * Usuwa z mapy wszystkie obrazy gleby poza `keep` (osierocone `<svg>` z `<clipPath>`/`<image>` po szybkim
 * przełączaniu warstw / działek). Wołane przy montowaniu nakładki i przez ParcelMap przy każdej zmianie warstwy.
 */
export function removeSoilOverlays(map: L.Map, keep?: Element | null) {
  map
    .getContainer()
    .querySelectorAll(`svg[${SOIL_ATTR}]`)
    .forEach((el) => {
      if (el === keep) return
      el.querySelector('image')?.removeAttribute('href')
      el.remove()
    })
}
