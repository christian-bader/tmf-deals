import { useState, useEffect, useMemo } from 'react'
import { supabase } from '../lib/supabaseClient'
import { ZipCodeMap } from './ZipCodeMap'

type ScrapeConfigRow = {
  zipcodes?: string[] | { zipcodes?: string[] } | null
  minimum_listing_price?: number
  maximum_listing_price?: number
}

/** Default zip list (same as scraper fallback) when DB has none or incomplete. */
const DEFAULT_ZIPCODES = [
  '92037', '92014', '92075', '92024', '92007', '92118', '92106', '92107',
  '92109', '92011', '92008', '92130', '92127', '92029',
  '92651', '92629', '92624', '92672', '92657', '92625', '92663', '92661',
  '92662', '92648', '92649',
]

/** Normalize zipcodes from jsonb: either { zipcodes: [...] } or raw array. */
function normalizeZipcodes(zips: ScrapeConfigRow['zipcodes']): string[] {
  if (zips == null) return []
  if (Array.isArray(zips)) {
    const list = zips.map((z) => String(z).trim()).filter(Boolean)
    return list.length ? list : []
  }
  if (typeof zips === 'object') {
    const inner = (zips as { zipcodes?: unknown }).zipcodes
    if (Array.isArray(inner)) {
      const list = inner.map((z) => String(z).trim()).filter(Boolean)
      return list.length ? list : []
    }
  }
  return []
}

function zipcodesToText(zips: string[] | null | undefined): string {
  if (!zips || !Array.isArray(zips)) return ''
  return zips.map((z) => String(z).trim()).filter(Boolean).join('\n')
}

function textToZipcodes(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((z) => z.trim())
    .filter(Boolean)
}

const usdFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
})

function formatUSD(n: number): string {
  if (Number.isNaN(n)) return ''
  return usdFormatter.format(n)
}

function parseUSD(s: string): number {
  const digits = s.replace(/[^0-9]/g, '')
  return digits ? Number(digits) : 0
}

export function ScrapeConfigButton() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedZipcodes, setSelectedZipcodes] = useState<string[]>([])
  const [zipcodesText, setZipcodesText] = useState('')
  const [minPrice, setMinPrice] = useState(1_500_000)
  const [maxPrice, setMaxPrice] = useState(20_000_000)

  const selectedZipSet = useMemo(() => new Set(selectedZipcodes), [selectedZipcodes])

  function toggleZip(zip: string) {
    setSelectedZipcodes((prev) => {
      const next = prev.includes(zip) ? prev.filter((z) => z !== zip) : [...prev, zip].sort()
      setZipcodesText(next.join('\n'))
      return next
    })
  }

  useEffect(() => {
    if (!open) return
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) setOpen(false)
    }
    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  }, [open, saving])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    supabase
      .from('scrape_configuration')
      .select('zipcodes, minimum_listing_price, maximum_listing_price')
      .eq('active', true)
      .limit(1)
      .maybeSingle()
      .then(({ data, error: e }) => {
        setLoading(false)
        if (e) {
          setError(e.message)
          return
        }
        const row = data as ScrapeConfigRow | null
        const zips = normalizeZipcodes(row?.zipcodes ?? null)
        const initialZips = zips.length > 0 ? zips : [...DEFAULT_ZIPCODES]
        setSelectedZipcodes(initialZips)
        setZipcodesText(initialZips.join('\n'))
        setMinPrice(Number(row?.minimum_listing_price) || 1_500_000)
        setMaxPrice(Number(row?.maximum_listing_price) || 20_000_000)
      })
  }, [open])

  async function handleSave() {
    const zipsToSave = selectedZipcodes.length > 0 ? selectedZipcodes : textToZipcodes(zipcodesText)
    if (zipsToSave.length === 0) {
      setError('Select at least one zip code on the map or enter zip codes.')
      return
    }
    const min = Number(minPrice)
    const max = Number(maxPrice)
    if (Number.isNaN(min) || Number.isNaN(max) || min < 0 || max < min) {
      setError('Min and max price must be valid numbers with min ≤ max.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const { error: updateErr } = await supabase
        .from('scrape_configuration')
        .update({ active: false })
        .eq('active', true)
      if (updateErr) throw updateErr

      const { error: insertErr } = await supabase.from('scrape_configuration').insert({
        zipcodes: { zipcodes: zipsToSave },
        minimum_listing_price: min,
        maximum_listing_price: max,
        active: true,
      })
      if (insertErr) throw insertErr
      setOpen(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save configuration.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-lg border border-[#e5e7eb] bg-white px-3 py-1.5 text-[12px] font-medium text-[#374151] shadow-sm transition-colors hover:bg-[#f9fafb] hover:text-[#1a1d21]"
        title="Edit search configuration"
      >
        Search Configuration
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !saving && setOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="scrape-config-title"
        >
          <div
            className="flex w-full max-w-4xl flex-col rounded-xl border border-[#e5e7eb] bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b border-[#e5e7eb] p-5">
              <h2 id="scrape-config-title" className="text-[1.125rem] font-semibold text-[#1a1d21]">
                Search configuration
              </h2>
              <p className="mt-1 text-[13px] text-[#6b7280]">
                Click zip codes on the map to select or deselect. Saving creates a new config and deactivates the current one.
              </p>
            </div>

            {loading ? (
              <div className="flex min-h-[320px] items-center justify-center p-8 text-sm text-[#6b7280]">
                Loading current config…
              </div>
            ) : (
              <div className="flex flex-col gap-0 sm:flex-row">
                <div className="h-[320px] w-full shrink-0 sm:w-[55%]">
                  <ZipCodeMap
                    selectedZips={selectedZipSet}
                    onToggleZip={toggleZip}
                  />
                </div>
                <div className="flex h-[320px] min-w-0 flex-1 flex-col border-t border-[#e5e7eb] p-5 sm:border-t-0 sm:border-l">
                  <div className="flex min-h-0 flex-1 flex-col gap-4">
                    <div className="min-h-0 flex-1 flex flex-col">
                      <label htmlFor="scrape-zipcodes" className="block text-[13px] font-medium text-[#374151]">
                        Zip codes ({selectedZipcodes.length} selected) — or edit as text
                      </label>
                      <textarea
                        id="scrape-zipcodes"
                        value={zipcodesText}
                        onChange={(e) => {
                          const text = e.target.value
                          setZipcodesText(text)
                          const parsed = textToZipcodes(text)
                          if (parsed.length > 0) setSelectedZipcodes(parsed)
                        }}
                        onBlur={() => setZipcodesText(selectedZipcodes.join('\n'))}
                        className="mt-1 min-h-0 flex-1 w-full resize-none rounded-lg border border-[#e5e7eb] px-3 py-2 text-sm text-[#1a1d21] focus:border-[#1a1d21] focus:outline-none focus:ring-1 focus:ring-[#1a1d21]"
                        placeholder={'92037\n92014\n92651'}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="scrape-min-price" className="block text-[13px] font-medium text-[#374151]">
                      Min price
                    </label>
                    <input
                      id="scrape-min-price"
                      type="text"
                      inputMode="numeric"
                      value={formatUSD(minPrice)}
                      onChange={(e) => setMinPrice(parseUSD(e.target.value))}
                      placeholder="$0"
                      className="mt-1 w-full rounded-lg border border-[#e5e7eb] px-3 py-2 text-sm text-[#1a1d21] focus:border-[#1a1d21] focus:outline-none focus:ring-1 focus:ring-[#1a1d21]"
                    />
                  </div>
                  <div>
                    <label htmlFor="scrape-max-price" className="block text-[13px] font-medium text-[#374151]">
                      Max price
                    </label>
                    <input
                      id="scrape-max-price"
                      type="text"
                      inputMode="numeric"
                      value={formatUSD(maxPrice)}
                      onChange={(e) => setMaxPrice(parseUSD(e.target.value))}
                      placeholder="$0"
                      className="mt-1 w-full rounded-lg border border-[#e5e7eb] px-3 py-2 text-sm text-[#1a1d21] focus:border-[#1a1d21] focus:outline-none focus:ring-1 focus:ring-[#1a1d21]"
                    />
                  </div>
                </div>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="px-5 pb-2">
                <p className="text-[13px] text-red-600" role="alert">
                  {error}
                </p>
              </div>
            )}

            <div className="flex justify-end gap-2 border-t border-[#e5e7eb] p-5">
              <button
                type="button"
                onClick={() => setOpen(false)}
                disabled={saving}
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-[#6b7280] hover:bg-[#f3f4f6] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={loading || saving}
                className="rounded-lg bg-[#1a1d21] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#374151] disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save new config'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
