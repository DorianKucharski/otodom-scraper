import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import type { AdSummary } from '../api/types'
import { formatMoney } from './AdCard'

interface MapViewProps {
  ads: AdSummary[]
  onSelect: (adId: number) => void
}

const POLAND_CENTER: [number, number] = [52.0, 19.5]

function markerColor(score: number | null | undefined): string {
  if (score == null) return '#94a3b8'
  if (score <= 3) return '#dc2626'
  if (score <= 5) return '#f59e0b'
  if (score <= 7) return '#eab308'
  if (score <= 8) return '#65a30d'
  return '#16a34a'
}

export function MapView({ ads, onSelect }: MapViewProps) {
  const located = ads.filter((ad) => ad.latitude !== null && ad.longitude !== null)
  const center: [number, number] = located.length
    ? [located[0].latitude as number, located[0].longitude as number]
    : POLAND_CENTER

  return (
    <MapContainer center={center} zoom={located.length ? 12 : 6} className="map-view">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {located.map((ad) => (
        <CircleMarker
          key={ad.id}
          center={[ad.latitude as number, ad.longitude as number]}
          radius={9}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: markerColor(ad.evaluation?.overall_score),
            fillOpacity: 0.9,
          }}
          eventHandlers={{ click: () => onSelect(ad.id) }}
        >
          <Popup>
            <strong>{ad.title}</strong>
            <br />
            {formatMoney(ad.price_value)} · {formatMoney(ad.price_per_m2, 'zł/m²')}
            <br />
            Ocena AI: {ad.evaluation?.overall_score ?? 'brak'}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
