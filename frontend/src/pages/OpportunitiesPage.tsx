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
  email: SuggestedEmail | null
}

async function fetchOpportunitiesWithEmails(): Promise<OpportunityWithEmail[]> {
  const { data: opps, error: oppError } = await supabase
    .from('outreach_opportunities')
    .select('*')
    .limit(200)

  if (oppError) throw oppError

  const opportunities = (opps ?? []) as OutreachOpportunity[]
  if (opportunities.length === 0) return []

  const brokerIds = opportunities.map((o) => o.broker_id)

  const { data: emails, error: emailError } = await supabase
    .from('suggested_emails')
    .select('id,broker_id,subject,body_content,new_listing_ids,created_at,status')
    .in('broker_id', brokerIds)
    .in('status', ['draft', 'approved'])

  if (emailError) throw emailError

  const latestByBroker = new Map<string, SuggestedEmail>()
  ;(emails ?? []).forEach((raw) => {
    const e = raw as SuggestedEmail & { status: string }
    const existing = latestByBroker.get(e.broker_id)
    if (!existing || existing.created_at < e.created_at) {
      latestByBroker.set(e.broker_id, e)
    }
  })

  const rows: OpportunityWithEmail[] = opportunities.map((o) => {
    const listings = (o.listings ?? []) as ListingSummary[]
    const listingCount = listings.length
    const pendingCount = listings.filter((l) => {
      const status = (l.status ?? '').toLowerCase()
      return status === 'pending' || status === 'contingent'
    }).length
    const email = latestByBroker.get(o.broker_id) ?? null
    return { ...o, listings, listingCount, pendingCount, email }
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
          <h2 className="text-lg font-semibold text-slate-900">
            Outreach Opportunities
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Emails ready to go, ranked by the number of listings each broker is
            touching.
          </p>
        </div>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {isError && (
        <p className="text-sm text-rose-500">
          Failed to load opportunities: {(error as Error).message}
        </p>
      )}

      {data && data.length > 0 && (
        <>
          <div className="h-[520px] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_60px_rgba(15,23,42,0.12)]">
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Brokers by pending listings — click a row to open details
            </div>
            <div className="h-[calc(100%-48px)] overflow-auto">
              <table className="min-w-full border-separate border-spacing-0 text-sm">
                <thead className="sticky top-0 bg-slate-50 text-slate-500">
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
                        className={`cursor-pointer border-t border-slate-100 transition-colors hover:bg-slate-50 ${
                          isActive ? 'bg-slate-100' : ''
                        }`}
                        onClick={() => setSelectedBrokerId(row.broker_id)}
                      >
                        <td className="px-4 py-2 align-top text-slate-900">
                          <div className="text-[13px] font-medium">
                            {row.name ?? '(no name)'}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {row.brokerage_name ?? '—'}
                          </div>
                        </td>
                        <td className="px-4 py-2 align-top text-[11px] text-slate-600">
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
                        <td className="px-3 py-2 align-top text-right text-[11px] font-semibold text-slate-800">
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
                className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-6 py-3">
                  <h2 id="broker-detail-title" className="text-sm font-semibold text-slate-900">
                    {selected.name ?? '(no name)'}
                  </h2>
                  <button
                    type="button"
                    onClick={() => setSelectedBrokerId(null)}
                    className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-700"
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
                    {selected.email ? (
                      <div className="mt-3 space-y-2">
                        <p className="text-[11px] font-semibold text-slate-900">
                          {selected.email.subject || '(no subject)'}
                        </p>
                        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-white px-3 py-2 text-[11px] leading-relaxed text-slate-700">
                          {selected.email.body_content || '(no body)'}
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
                      const all = selected.listings ?? []
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

