import { useState, useEffect, useCallback, useMemo } from 'react'
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet'
import type { GeoJsonObject, Feature, Geometry } from 'geojson'

const MAP_CENTER: [number, number] = [33.5, -117.4]
const DEFAULT_ZOOM = 7

type ZipCodeMapProps = {
  selectedZips: Set<string>
  onToggleZip: (zip: string) => void
}

type ZipFeature = Feature<Geometry, { zip?: string; ZCTA5CE20?: string }>

function getZipFromFeature(feature: ZipFeature): string {
  const p = feature.properties
  return (p?.zip ?? p?.ZCTA5CE20 ?? '').toString()
}

export function ZipCodeMap({ selectedZips, onToggleZip }: ZipCodeMapProps) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    setLoadError(null)
    fetch('/socal_zctas.geojson')
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load map (${r.status})`)
        return r.json()
      })
      .then(setGeojson)
      .catch((e) => setLoadError(e instanceof Error ? e.message : 'Failed to load map'))
  }, [])

  const style = useCallback(
    (feature?: ZipFeature) => {
      const zip = feature ? getZipFromFeature(feature) : ''
      const selected = zip && selectedZips.has(zip)
      return {
        color: selected ? '#1a1d21' : '#94a3b8',
        weight: selected ? 2 : 1,
        fillColor: selected ? '#2563eb' : '#e2e8f0',
        fillOpacity: selected ? 0.65 : 0.35,
      }
    },
    [selectedZips],
  )

  const onEachFeature = useCallback(
    (feature: ZipFeature, layer: L.Layer) => {
      const zip = getZipFromFeature(feature)
      if (!zip) return
      layer.on({
        click: () => onToggleZip(zip),
      })
      const layerWithBind = layer as L.Layer & { bindTooltip: (content: string) => void }
      if (layerWithBind.bindTooltip) {
        layerWithBind.bindTooltip(
          `${zip} ${selectedZips.has(zip) ? '(selected – click to deselect)' : '(click to select)'}`,
          { direction: 'top' },
        )
      }
    },
    [onToggleZip, selectedZips],
  )

  const key = useMemo(() => (geojson ? 'loaded' : 'empty'), [geojson])

  if (loadError) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] bg-[#f9fafb] p-4 text-center">
        <p className="text-sm font-medium text-[#374151]">Southern California ZIP map</p>
        <p className="text-[13px] text-[#6b7280]">
          Generate the map by running:
          <br />
          <code className="mt-1 block rounded bg-[#e5e7eb] px-2 py-1 text-xs">
            python scripts/boundaries/census/build_socal_zctas.py
          </code>
          <span className="mt-2 block text-[12px]">
            (Requires TIGER/Line ZCTA shapefile; see script for download link.)
          </span>
        </p>
        <p className="text-[12px] text-red-600">{loadError}</p>
      </div>
    )
  }

  if (!geojson) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-lg border border-[#e5e7eb] bg-[#f9fafb]">
        <p className="text-sm text-[#6b7280]">Loading Southern California ZIP boundaries…</p>
      </div>
    )
  }

  return (
    <div className="h-full w-full overflow-hidden rounded-lg border border-[#e5e7eb] bg-[#f9fafb]">
      <MapContainer
        key={key}
        center={MAP_CENTER}
        zoom={DEFAULT_ZOOM}
        className="h-full w-full"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON
          data={geojson}
          style={style}
          onEachFeature={onEachFeature}
        />
      </MapContainer>
    </div>
  )
}
