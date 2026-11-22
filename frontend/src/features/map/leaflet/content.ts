/**
 * Pojemnik na treść dymka renderowaną przez React (portal). `display: contents` – sam pojemnik nie wpływa
 * na układ, Leaflet mierzy dymek tak, jakby treść była wstawiona bezpośrednio.
 */
export function createContentNode(): HTMLDivElement {
  const el = document.createElement('div')
  el.style.display = 'contents'
  return el
}
