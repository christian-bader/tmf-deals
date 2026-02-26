import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient.ts'

type ListingSummary = {
  id: string
  address: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
  price: number | null
  status: string | null
  sale_date: string | null
  source_url?: string | null
}

type OutreachOpportunity = {
  broker_id: string
  name: string | null
  email: string | null
  brokerage_name: string | null
  last_contacted_at: string | null
  listings: ListingSummary[] | null
}

type SuggestedEmail = {
  id: string
  broker_id: string
  subject: string | null
  body_content: string | null
  new_listing_ids: string[] | null
  created_at: string
}

type OpportunityWithEmail = OutreachOpportunity & {
  listingCount: number
  pendingCount: number
  suggestedEmail: SuggestedEmail | null
}

/** Normalize a raw listing object so it has `id` and consistent keys (view may return snake_case). */
function normalizeListing(raw: unknown): ListingSummary | null {
  if (raw == null || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const id = (o.id ?? o.listing_id ?? '') as string
  if (!id) return null
  return {
    id,
    address: (o.address ?? o.Address ?? null) as string | null,
    city: (o.city ?? o.City ?? null) as string | null,
    state: (o.state ?? o.State ?? null) as string | null,
    zip: (o.zip ?? o.Zip ?? null) as string | null,
    price: typeof o.price === 'number' ? o.price : (o.Price != null ? Number(o.Price) : null),
    status: (o.status ?? o.Status ?? null) as string | null,
    sale_date: (o.sale_date ?? null) as string | null,
    source_url: (o.source_url ?? null) as string | null,
  }
}

function toListingList(raw: unknown): ListingSummary[] {
  if (Array.isArray(raw)) {
    return raw.map(normalizeListing).filter((l): l is ListingSummary => l != null)
  }
  if (raw && typeof raw === 'object') {
    const one = normalizeListing(raw)
    return one ? [one] : []
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown
      return Array.isArray(parsed)
        ? (parsed as unknown[]).map(normalizeListing).filter((l): l is ListingSummary => l != null)
        : []
    } catch {
      return []
    }
  }
  return []
}

async function fetchOpportunitiesWithEmails(): Promise<OpportunityWithEmail[]> {
  const { data: opps, error: oppError } = await supabase
    .from('outreach_opportunities')
    .select('*')
    .limit(200)

  if (oppError) throw new Error(oppError.message ?? 'Failed to load opportunities')

  const opportunities = (opps ?? []) as OutreachOpportunity[]
  if (opportunities.length === 0) return []

  const brokerIds = opportunities
    .map((o) => o.broker_id)
    .filter((id): id is string => id != null && id !== '')

  let emails: unknown[] = []
  if (brokerIds.length > 0) {
    const { data: emailData, error: emailError } = await supabase
      .from('suggested_emails')
      .select('id,broker_id,subject,body_content,new_listing_ids,created_at,status')
      .in('broker_id', brokerIds)
      .in('status', ['draft', 'approved'])

    if (emailError) throw new Error(emailError.message ?? 'Failed to load suggested emails')
    emails = emailData ?? []
  }

  const latestByBroker = new Map<string, SuggestedEmail>()
  emails.forEach((raw) => {
    const e = raw as SuggestedEmail & { status: string }
    const existing = latestByBroker.get(e.broker_id)
    if (!existing || existing.created_at < e.created_at) {
      latestByBroker.set(e.broker_id, e)
    }
  })

  const rows: OpportunityWithEmail[] = opportunities.map((o) => {
    const listings = toListingList(o.listings)
    const listingCount = listings.length
    const pendingCount = listings.filter((l) => {
      const status = (l.status ?? '').toLowerCase()
      return status === 'pending' || status === 'contingent'
    }).length
    const suggestedEmail = latestByBroker.get(o.broker_id) ?? null
    return { ...o, listings, listingCount, pendingCount, suggestedEmail }
  })

  rows.sort((a, b) => {
    if (b.pendingCount !== a.pendingCount) {
      return b.pendingCount - a.pendingCount
    }
    return b.listingCount - a.listingCount
  })
  return rows
}

export function OpportunitiesPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['outreach-opportunities-with-emails'],
    queryFn: fetchOpportunitiesWithEmails,
  })

  const [selectedBrokerId, setSelectedBrokerId] = useState<string | null>(null)

  const selected =
    data && selectedBrokerId
      ? data.find((d) => d.broker_id === selectedBrokerId) ?? null
      : null

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
            Outreach Opportunities
          </h2>
          <p className="mt-0.5 text-[13px] text-[#6b7280]">
            Emails ready to go, ranked by listings per broker.
          </p>
        </div>
      </div>

      {isLoading && <p className="text-[13px] text-[#6b7280]">Loading…</p>}
      {isError && (
        <p className="text-[13px] text-[#dc2626]">
          Failed to load opportunities: {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data && data.length === 0 && !isLoading && (
        <div className="rounded-xl border border-[#e5e7eb] bg-white p-8 text-center shadow-panel">
          <p className="text-[13px] text-[#6b7280]">No outreach opportunities right now.</p>
          <p className="mt-1 text-[12px] text-[#9ca3af]">When brokers have pending listings and draft/approved emails, they’ll appear here.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <>
          <div className="h-[520px] overflow-hidden rounded-xl border border-[#e5e7eb] bg-white shadow-panel">
            <div className="border-b border-[#e5e7eb] bg-[#f9fafb] px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
              Brokers by pending listings — click a row to open details
            </div>
            <div className="h-[calc(100%-48px)] overflow-auto">
              <table className="min-w-full border-separate border-spacing-0 text-sm">
                <thead className="sticky top-0 bg-[#f9fafb] text-[#6b7280]">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Broker</th>
                    <th className="px-4 py-2 text-left font-medium">Email</th>
                    <th className="px-3 py-2 text-right font-medium">Deals</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => {
                    const isActive =
                      (selected?.broker_id ?? null) === row.broker_id
                    return (
                      <tr
                        key={row.broker_id}
                        className={`cursor-pointer border-t border-[#f3f4f6] transition-colors hover:bg-[#f9fafb] ${
                          isActive ? 'bg-[#f3f4f6]' : ''
                        }`}
                        onClick={() => setSelectedBrokerId(row.broker_id)}
                      >
                        <td className="px-4 py-2 align-top text-[#1a1d21]">
                          <div className="text-[13px] font-medium">
                            {row.name ?? '(no name)'}
                          </div>
                          <div className="mt-1 text-[11px] text-[#6b7280]">
                            {row.brokerage_name ?? '—'}
                          </div>
                        </td>
                        <td className="px-4 py-2 align-top text-[11px] text-[#374151]">
                          {row.email ?? '—'}
                          <div className="mt-1 text-[10px] text-slate-400">
                            Last contacted:{' '}
                            {row.last_contacted_at
                              ? new Date(
                                  row.last_contacted_at,
                                ).toLocaleDateString()
                              : 'never'}
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top text-right text-[11px] font-semibold text-[#1a1d21]">
                          <div>
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                              {row.pendingCount} pending
                            </span>
                          </div>
                          <div className="mt-1 text-[10px] text-slate-400">
                            {row.listingCount} total
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Broker detail popup */}
          {selected && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
              onClick={() => setSelectedBrokerId(null)}
              role="dialog"
              aria-modal="true"
              aria-labelledby="broker-detail-title"
            >
              <div
                className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-xl border border-[#e5e7eb] bg-white shadow-panel-hover"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between border-b border-[#e5e7eb] bg-[#f9fafb] px-6 py-3">
                  <h2 id="broker-detail-title" className="text-sm font-semibold tracking-[-0.02em] text-[#1a1d21]">
                    {selected.name ?? '(no name)'}
                  </h2>
                  <button
                    type="button"
                    onClick={() => setSelectedBrokerId(null)}
                    className="rounded-lg p-2 text-[#6b7280] transition-colors hover:bg-[#e5e7eb] hover:text-[#1a1d21]"
                    aria-label="Close"
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="max-h-[calc(90vh-56px)] overflow-auto px-6 py-5 text-sm">
                  <header className="mb-5 flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] text-slate-500">
                        {selected.brokerage_name ?? 'No brokerage on file'}
                      </p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        {selected.email ?? 'No email on file'}
                      </p>
                    </div>
                    <div className="space-y-2 text-right">
                      <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] uppercase tracking-wide text-slate-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        {selected.pendingCount} pending
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {selected.listingCount} total listings
                      </div>
                    </div>
                  </header>

                  <section className="mb-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Suggested email
                      </h4>
                      <span className="text-[10px] text-slate-400">
                        Last contacted:{' '}
                        {selected.last_contacted_at
                          ? new Date(
                              selected.last_contacted_at,
                            ).toLocaleDateString()
                          : 'never'}
                      </span>
                    </div>
                    {selected.suggestedEmail ? (
                      <div className="mt-3 space-y-2">
                        <p className="text-[11px] font-semibold text-slate-900">
                          {selected.suggestedEmail.subject || '(no subject)'}
                        </p>
                        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-white px-3 py-2 text-[11px] leading-relaxed text-slate-700">
                          {selected.suggestedEmail.body_content || '(no body)'}
                        </pre>
                      </div>
                    ) : (
                      <p className="mt-3 text-[11px] text-slate-500">
                        No suggested email yet for this broker.
                      </p>
                    )}
                  </section>

                  <section>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <h4 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Pending listings (priority)
                      </h4>
                    </div>
                    {(() => {
                      const all = toListingList(selected.listings).filter(
                        (l): l is ListingSummary => l != null && typeof l === 'object' && 'id' in l,
                      )
                      const pending = all.filter((l) => {
                        const status = (l.status ?? '').toLowerCase()
                        return status === 'pending' || status === 'contingent'
                      })
                      const active = all.filter(
                        (l) => (l.status ?? '').toLowerCase() === 'active',
                      )
                      return (
                        <>
                          <div className="grid gap-2 pr-1 md:grid-cols-2">
                            {pending.map((l) => (
                              <article
                                key={l.id}
                                className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2.5"
                              >
                                <p className="text-[11px] font-semibold text-slate-900">
                                  {l.address ?? '(no address)'}
                                </p>
                                <p className="mt-0.5 text-[10px] text-slate-500">
                                  {[l.city, l.state, l.zip]
                                    .filter(Boolean)
                                    .join(', ')}
                                </p>
                                <p className="mt-1 text-[11px] text-slate-900">
                                  {typeof l.price === 'number'
                                    ? l.price.toLocaleString('en-US', {
                                        style: 'currency',
                                        currency: 'USD',
                                        maximumFractionDigits: 0,
                                      })
                                    : 'Price N/A'}
                                </p>
                                <p className="mt-0.5 text-[10px] text-slate-500">
                                  Status: {l.status ?? '—'} · Closed:{' '}
                                  {l.sale_date
                                    ? new Date(l.sale_date).toLocaleDateString()
                                    : '—'}
                                </p>
                                {l.source_url && (
                                  <a
                                    href={l.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="mt-1 inline-flex text-[10px] font-medium text-sky-600 hover:underline"
                                  >
                                    View on Redfin
                                  </a>
                                )}
                              </article>
                            ))}
                            {pending.length === 0 && (
                              <p className="text-[11px] text-slate-500">
                                No pending listings for this broker.
                              </p>
                            )}
                          </div>
                          <div className="mt-4">
                            <div className="mb-2 flex items-center justify-between gap-2">
                              <h4 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                                Active listings
                              </h4>
                            </div>
                            <div className="grid gap-2 pr-1 md:grid-cols-2">
                              {active.map((l) => (
                                <article
                                  key={l.id}
                                  className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
                                >
                                  <p className="text-[11px] font-semibold text-slate-900">
                                    {l.address ?? '(no address)'}
                                  </p>
                                  <p className="mt-0.5 text-[10px] text-slate-500">
                                    {[l.city, l.state, l.zip]
                                      .filter(Boolean)
                                      .join(', ')}
                                  </p>
                                  <p className="mt-1 text-[11px] text-slate-900">
                                    {typeof l.price === 'number'
                                      ? l.price.toLocaleString('en-US', {
                                          style: 'currency',
                                          currency: 'USD',
                                          maximumFractionDigits: 0,
                                        })
                                      : 'Price N/A'}
                                  </p>
                                  <p className="mt-0.5 text-[10px] text-slate-500">
                                    Status: {l.status ?? '—'} · Closed:{' '}
                                    {l.sale_date
                                      ? new Date(
                                          l.sale_date,
                                        ).toLocaleDateString()
                                      : '—'}
                                  </p>
                                  {l.source_url && (
                                    <a
                                      href={l.source_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="mt-1 inline-flex text-[10px] font-medium text-sky-600 hover:underline"
                                    >
                                      View on Redfin
                                    </a>
                                  )}
                                </article>
                              ))}
                              {active.length === 0 && (
                                <p className="text-[11px] text-slate-500">
                                  No active listings for this broker.
                                </p>
                              )}
                            </div>
                          </div>
                        </>
                      )
                    })()}
                  </section>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

