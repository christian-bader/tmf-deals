import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { supabase } from '../lib/supabaseClient.ts'

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
}

async function fetchListings() {
  const { data, error } = await supabase
    .from('listings')
    .select('id,address,city,state,zip,price,status,sale_date')
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
          <h2 className="text-lg font-semibold text-slate-900">Listings</h2>
          <p className="mt-1 text-sm text-slate-500">
            Explore active, pending, and sold properties on the map or in the
            list.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 shadow-sm">
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

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {isError && (
        <p className="text-sm text-rose-500">
          Failed to load listings: {(error as Error).message}
        </p>
      )}

      {filtered && filtered.length > 0 && (
        <div className="flex h-[520px] gap-6 rounded-3xl bg-white/80 p-4 shadow-[0_18px_60px_rgba(15,23,42,0.12)] ring-1 ring-slate-200 backdrop-blur-sm">
          {/* Map */}
          <div className="w-[55%] overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
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
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  )
                })}
              </MapContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                No coordinates available for these listings yet.
              </div>
            )}
          </div>

          {/* List */}
          <div className="flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Listings ({filtered.length})
            </div>
            <div className="h-full overflow-auto">
              <table className="min-w-full border-separate border-spacing-0 text-sm">
                <thead className="sticky top-0 bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Address</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Price</th>
                    <th className="px-3 py-2 text-left font-medium">
                      Sale Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((l) => (
                    <tr
                      key={l.id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-3 py-2 align-top">
                        <div className="text-slate-900">
                          {l.address || '(no address)'}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {[l.city, l.state, l.zip].filter(Boolean).join(', ')}
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-xs font-medium uppercase tracking-wide text-slate-600">
                        {l.status}
                      </td>
                      <td className="px-3 py-2 align-top text-right text-slate-900">
                        {typeof l.price === 'number'
                          ? l.price.toLocaleString('en-US', {
                              style: 'currency',
                              currency: 'USD',
                              maximumFractionDigits: 0,
                            })
                          : '—'}
                      </td>
                      <td className="px-3 py-2 align-top text-slate-600">
                        {l.sale_date
                          ? new Date(l.sale_date).toLocaleDateString()
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

