import { useEffect } from 'react'
import { CircleMarker, Polygon, Polyline, useMap } from 'react-leaflet'

/**
 * Rysowane pole na mapie: wielokąt z dotychczasowych punktów (przerywany obrys), wierzchołki jako kropki.
 * Klik w pierwszy wierzchołek (przy ≥ 3 punktach) = zamknięcie pola („Gotowe”). Rysowane wewnątrz MapContainer.
 */
export function DrawLayer({ points, onClose }: { points: [number, number][]; onClose: () => void }) {
  const map = useMap()
  // szybkie klikanie wierzchołków nie może przybliżać mapy
  useEffect(() => {
    map.doubleClickZoom.disable()
    return () => {
      map.doubleClickZoom.enable()
    }
  }, [map])
  const latlngs = points.map(([lon, lat]) => [lat, lon] as [number, number])
  const style = { color: '#FFFFFF', weight: 3, dashArray: '6 6', fillColor: '#E2A23B', fillOpacity: 0.25 }
  return (
    <>
      {points.length >= 3 ? (
        <Polygon positions={latlngs} pathOptions={style} interactive={false} />
      ) : (
        points.length === 2 && <Polyline positions={latlngs} pathOptions={style} interactive={false} />
      )}
      {latlngs.map((p, i) => (
        <CircleMarker
          key={`${p[0]}-${p[1]}-${i}`}
          center={p}
          radius={i === 0 && points.length >= 3 ? 9 : 6}
          interactive={i === 0 && points.length >= 3}
          bubblingMouseEvents={false}
          eventHandlers={i === 0 ? { click: () => onClose() } : undefined}
          pathOptions={{ color: '#FFFFFF', weight: 2.5, fillColor: i === 0 ? '#1F4D3A' : '#E2A23B', fillOpacity: 1 }}
        />
      ))}
    </>
  )
}
