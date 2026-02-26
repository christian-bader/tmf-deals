import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { supabase } from '../lib/supabaseClient.ts'

function OutLinkIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
  )
}

type Listing = {
  id: string
  address: string | null
  city: string | null
  state: string | null
  zip: string | null
  price: number | null
  status: string | null
  sale_date: string | null
  latitude?: number | null
  longitude?: number | null
  source_url?: string | null
}

async function fetchListings() {
  const { data, error } = await supabase
    .from('listings')
    .select('id,address,city,state,zip,price,status,sale_date,latitude,longitude,source_url')
    .order('sale_date', { ascending: false })
    .limit(300)

  if (error) throw error
  return data as Listing[]
}

export function ListingsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['listings'],
    queryFn: fetchListings,
  })

  const [statusFilter, setStatusFilter] = useState<
    'all' | 'active' | 'pending' | 'sold'
  >('all')

  const filtered = useMemo(() => {
    if (!data) return []
    return data.filter((l) => {
      if (statusFilter === 'all') return true
      const s = (l.status ?? '').toLowerCase()
      if (statusFilter === 'pending') {
        return s === 'pending' || s === 'contingent'
      }
      return s === statusFilter
    })
  }, [data, statusFilter])

  const mapCenter: [number, number] | null = useMemo(() => {
    const firstWithCoords = filtered.find(
      (l) => typeof l.latitude === 'number' && typeof l.longitude === 'number',
    )
    if (firstWithCoords) {
      return [
        firstWithCoords.latitude as number,
        firstWithCoords.longitude as number,
      ]
    }
    return null
  }, [filtered])

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
            Listings
          </h2>
          <p className="mt-0.5 text-[13px] text-[#6b7280]">
            Explore active, pending, and sold properties on the map or in the list.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-lg border border-[#e5e7eb] bg-white px-3 py-1.5 text-[12px] text-[#374151] shadow-panel">
          <span>Filter:</span>
          <select
            className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 focus:outline-none"
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(
                e.target.value as 'all' | 'active' | 'pending' | 'sold',
              )
            }
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="pending">Pending / Contingent</option>
            <option value="sold">Sold</option>
          </select>
        </div>
      </div>

      {isLoading && <p className="text-[13px] text-[#6b7280]">Loading…</p>}
      {isError && (
        <p className="text-[13px] text-[#dc2626]">
          Failed to load listings: {(error as Error).message}
        </p>
      )}

      {filtered && filtered.length > 0 && (
        <div className="flex h-[520px] gap-5 rounded-xl border border-[#e5e7eb] bg-white p-4 shadow-panel">
          {/* Map */}
          <div className="w-[55%] overflow-hidden rounded-lg border border-[#e5e7eb] bg-[#f9fafb]">
            {mapCenter ? (
              <MapContainer
                center={mapCenter}
                zoom={11}
                className="h-full w-full"
                scrollWheelZoom={false}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {filtered.map((l) => {
                  if (
                    typeof l.latitude !== 'number' ||
                    typeof l.longitude !== 'number'
                  ) {
                    return null
                  }
                  const status = (l.status ?? '').toLowerCase()
                  const color =
                    status === 'pending' || status === 'contingent'
                      ? '#22c55e'
                      : status === 'active'
                        ? '#0ea5e9'
                        : '#64748b'
                  return (
                    <CircleMarker
                      key={l.id}
                      center={[l.latitude, l.longitude]}
                      radius={6}
                      pathOptions={{ color, fillColor: color, fillOpacity: 0.8 }}
                    >
                      <Tooltip direction="top">
                        <div className="text-[11px]">
                          <div className="font-semibold">
                            {l.address ?? '(no address)'}
                          </div>
                          <div className="text-slate-600">
                            {[l.city, l.state, l.zip]
                              .filter(Boolean)
                              .join(', ')}
                          </div>
                          <div className="mt-1">
                            {typeof l.price === 'number'
                              ? l.price.toLocaleString('en-US', {
                                  style: 'currency',
                                  currency: 'USD',
                                  maximumFractionDigits: 0,
                                })
                              : 'Price N/A'}
                          </div>
                          <div className="mt-0.5 text-slate-600">
                            Status: {l.status ?? '—'} · Closed:{' '}
                            {l.sale_date
                              ? new Date(l.sale_date).toLocaleDateString()
                              : '—'}
                          </div>
                          {l.source_url && l.source_url.startsWith('http') && (
                            <a
                              href={l.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-1 inline-flex items-center gap-1 font-medium text-sky-600 hover:underline"
                            >
                              <OutLinkIcon className="h-3.5 w-3.5" />
                              Open source
                            </a>
                          )}
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  )
                })}
              </MapContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-[13px] text-[#6b7280]">
                No coordinates available for these listings yet.
              </div>
            )}
          </div>

          {/* List */}
          <div className="flex-1 overflow-hidden rounded-lg border border-[#e5e7eb] bg-white">
            <div className="border-b border-[#e5e7eb] bg-[#f9fafb] px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
              Listings ({filtered.length})
            </div>
            <div className="h-full overflow-auto">
              <table className="min-w-full border-separate border-spacing-0 text-sm">
                <thead className="sticky top-0 bg-[#f9fafb] text-[#6b7280]">
                  <tr>
                    <th className="w-9 px-1 py-2" aria-label="Source link" />
                    <th className="px-3 py-2 text-left font-medium">Address</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Price</th>
                    <th className="px-3 py-2 text-left font-medium">
                      Sale Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((l) => {
                    const hasLink = Boolean(l.source_url && l.source_url.startsWith('http'))
                    return (
                      <tr
                        key={l.id}
                        className="border-t border-[#f3f4f6] hover:bg-[#f9fafb]"
                      >
                        <td className="px-1 py-2 align-top">
                          {hasLink ? (
                            <a
                              href={l.source_url!}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex rounded p-1.5 text-[#6b7280] hover:bg-[#e5e7eb] hover:text-sky-600"
                              title="Open listing source in new tab"
                              aria-label="Open listing source in new tab"
                            >
                              <OutLinkIcon />
                            </a>
                          ) : (
                            <span className="inline-flex rounded p-1.5 text-[#d1d5db]" title="No source link">
                              <OutLinkIcon />
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="text-[#1a1d21]">
                            {l.address || '(no address)'}
                          </div>
                          <div className="mt-0.5 text-xs text-[#6b7280]">
                            {[l.city, l.state, l.zip].filter(Boolean).join(', ')}
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top text-xs font-medium uppercase tracking-wide text-[#374151]">
                          {l.status}
                        </td>
                        <td className="px-3 py-2 align-top text-right text-[#1a1d21]">
                          {typeof l.price === 'number'
                            ? l.price.toLocaleString('en-US', {
                                style: 'currency',
                                currency: 'USD',
                                maximumFractionDigits: 0,
                              })
                            : '—'}
                        </td>
                        <td className="px-3 py-2 align-top text-[#6b7280]">
                          {l.sale_date
                            ? new Date(l.sale_date).toLocaleDateString()
                            : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

