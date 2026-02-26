import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

type BrokerInfo = {
  id: string
  name: string | null
  email: string | null
  brokerage_name: string | null
}

type SuggestedEmailRow = {
  id: string
  broker_id: string
  subject: string | null
  body_content: string | null
  status: string
  created_at: string
  /** Supabase may embed the relation as "brokers" (table name) or "broker" (alias). */
  brokers?: BrokerInfo | null
  broker?: BrokerInfo | null
}

/** Fetch pending listing count per broker_id from outreach_opportunities. */
async function fetchPendingCountByBroker(): Promise<Record<string, number>> {
  const { data, error } = await supabase
    .from('outreach_opportunities')
    .select('broker_id, listings')
    .limit(500)

  if (error) return {}
  const map: Record<string, number> = {}
  ;(data ?? []).forEach((row: { broker_id: string; listings?: unknown }) => {
    const list = toListingList(row.listings)
    const pending = list.filter((l) => {
      const s = (l.status ?? '').toLowerCase()
      return s === 'pending' || s === 'contingent'
    }).length
    const id = row.broker_id
    if (id) map[id] = pending
  })
  return map
}

async function fetchSuggestedEmails(): Promise<SuggestedEmailRow[]> {
  const [emailsRes, pendingCountByBroker] = await Promise.all([
    supabase
      .from('suggested_emails')
      .select('id, broker_id, subject, body_content, status, created_at, broker:brokers(id, name, email, brokerage_name)')
      .order('created_at', { ascending: false })
      .limit(100),
    fetchPendingCountByBroker(),
  ])

  const { data, error } = emailsRes
  if (error) throw new Error(error.message)
  const rows = (data ?? []) as unknown[]
  const parsed: SuggestedEmailRow[] = rows.map((row) => {
    const r = row as Record<string, unknown>
    const brokerRaw = r.broker ?? r.brokers
    const broker: BrokerInfo | null =
      brokerRaw && typeof brokerRaw === 'object' && !Array.isArray(brokerRaw)
        ? (brokerRaw as BrokerInfo)
        : Array.isArray(brokerRaw) && brokerRaw.length > 0
          ? (brokerRaw[0] as BrokerInfo)
          : null
    return {
      id: r.id,
      broker_id: r.broker_id,
      subject: r.subject,
      body_content: r.body_content,
      status: r.status,
      created_at: r.created_at,
      broker,
    } as SuggestedEmailRow
  })

  // Sort by importance: most pending listings first, then by created_at desc
  parsed.sort((a, b) => {
    const pendingA = pendingCountByBroker[a.broker_id] ?? 0
    const pendingB = pendingCountByBroker[b.broker_id] ?? 0
    if (pendingB !== pendingA) return pendingB - pendingA
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
  return parsed
}

async function fetchBrokerListings(brokerId: string): Promise<ListingSummary[]> {
  const { data, error } = await supabase
    .from('outreach_opportunities')
    .select('listings')
    .eq('broker_id', brokerId)
    .maybeSingle()

  if (error) return []
  const list = toListingList((data as { listings?: unknown } | null)?.listings)
  if (list.length === 0) return list

  // Enrich with source_url from listings table so outlink icons work
  const ids = list.map((l) => l.id).filter(Boolean)
  const { data: rows } = await supabase
    .from('listings')
    .select('id, source_url')
    .in('id', ids)

  const urlById = new Map<string, string | null>()
  ;(rows ?? []).forEach((r: { id: string; source_url?: string | null }) => {
    urlById.set(r.id, r.source_url ?? null)
  })

  return list.map((l) => ({
    ...l,
    source_url: urlById.get(l.id) ?? l.source_url,
  }))
}

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

export function EmailQueuePage() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggested-emails'],
    queryFn: fetchSuggestedEmails,
  })

  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null)

  const summary = (data ?? []).reduce(
    (acc, email) => {
      acc.total += 1
      acc[email.status as keyof typeof acc] =
        (acc[email.status as keyof typeof acc] ?? 0) + 1
      return acc
    },
    { total: 0, draft: 0, approved: 0, sent: 0, skipped: 0 } as {
      total: number
      draft: number
      approved: number
      sent: number
      skipped: number
    },
  )

  const selectedRow = data?.find((e) => e.id === selectedEmailId) ?? null

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
            Email Queue
          </h2>
          <p className="mt-0.5 text-[13px] text-[#6b7280]">
            Review, edit, and approve LLM-generated outreach emails.
          </p>
        </div>
      </div>

      {data && (
        <div className="inline-flex flex-wrap items-center gap-2 rounded-xl border border-[#e5e7eb] bg-white px-4 py-3 text-[12px] text-[#374151] shadow-panel">
          <span className="font-medium text-slate-700">
            Queue summary (draft + approved are ready to send):
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px]">
            Total: {summary.total}
          </span>
          <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] text-amber-700">
            Draft: {summary.draft}
          </span>
          <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
            Approved: {summary.approved}
          </span>
          <span className="rounded-full bg-sky-50 px-2 py-1 text-[11px] text-sky-700">
            Sent: {summary.sent}
          </span>
          <span className="rounded-full bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
            Skipped: {summary.skipped}
          </span>
        </div>
      )}

      {isLoading && <p className="text-[13px] text-[#6b7280]">Loading…</p>}
      {isError && (
        <p className="text-[13px] text-[#dc2626]">
          Failed to load emails: {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((email) => (
            <EmailQueueCard
              key={email.id}
              email={email}
              onOpen={() => setSelectedEmailId(email.id)}
              onStatusChange={() => queryClient.invalidateQueries({ queryKey: ['suggested-emails'] })}
            />
          ))}
        </div>
      )}

      {selectedRow && (
        <EmailDetailModal
          email={selectedRow}
          onClose={() => setSelectedEmailId(null)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['suggested-emails'] })
            setSelectedEmailId(null)
          }}
        />
      )}
    </div>
  )
}

function EmailQueueCard({
  email,
  onOpen,
  onStatusChange,
}: {
  email: SuggestedEmailRow
  onOpen: () => void
  onStatusChange: () => void
}) {
  const broker = email.broker ?? email.brokers
  const queryClient = useQueryClient()
  const statusMutation = useMutation({
    mutationFn: async (newStatus: string) => {
      const { error } = await supabase
        .from('suggested_emails')
        .update({ status: newStatus })
        .eq('id', email.id)
      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggested-emails'] })
      onStatusChange()
    },
  })

  const canApproveOrSkip = email.status === 'draft' || email.status === 'approved'

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      className="flex cursor-pointer flex-col rounded-xl border border-[#e5e7eb] bg-white p-4 shadow-panel transition-shadow hover:shadow-panel-hover"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
          {email.status}
        </span>
        <span className="text-[11px] text-[#6b7280]">
          {new Date(email.created_at).toLocaleString()}
        </span>
      </div>
      <div className="mt-2 border-b border-[#f3f4f6] pb-2">
        <p className="text-[11px] font-semibold text-[#374151]">
          To: {broker?.email ?? '(no email)'}
        </p>
        <p className="text-[11px] text-[#6b7280]">
          {broker?.name ?? '(no name)'}
          {broker?.brokerage_name ? ` · ${broker.brokerage_name}` : ''}
        </p>
      </div>
      <h3 className="mt-2 text-[13px] font-semibold text-[#1a1d21]">
        {email.subject || '(no subject)'}
      </h3>
      <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-[#f9fafb] p-3 text-[12px] leading-relaxed text-[#374151]">
        {email.body_content || '(no body)'}
      </pre>
      <div className="mt-3 flex gap-2" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            if (canApproveOrSkip) statusMutation.mutate('approved')
          }}
          disabled={!canApproveOrSkip || statusMutation.isPending}
          className="inline-flex flex-1 items-center justify-center rounded-lg bg-[#1a1d21] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-[#374151] disabled:opacity-50"
        >
          {statusMutation.isPending ? '…' : 'Approve'}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            if (canApproveOrSkip) statusMutation.mutate('skipped')
          }}
          disabled={!canApproveOrSkip || statusMutation.isPending}
          className="inline-flex flex-1 items-center justify-center rounded-lg border border-[#e5e7eb] bg-white px-3 py-1.5 text-[12px] font-medium text-[#374151] hover:bg-[#f9fafb] disabled:opacity-50"
        >
          Skip
        </button>
      </div>
      <p className="mt-2 text-[11px] text-[#9ca3af]">
        Click card to open details, listings, and edit
      </p>
    </article>
  )
}

function EmailDetailModal({
  email,
  onClose,
  onSaved,
}: {
  email: SuggestedEmailRow
  onClose: () => void
  onSaved: () => void
}) {
  const broker = email.broker ?? email.brokers
  const { data: listings, isLoading: listingsLoading } = useQuery({
    queryKey: ['broker-listings', email.broker_id],
    queryFn: () => fetchBrokerListings(email.broker_id),
    enabled: !!email.broker_id,
  })

  const [subject, setSubject] = useState(email.subject ?? '')
  const [body, setBody] = useState(email.body_content ?? '')
  const queryClient = useQueryClient()

  const updateMutation = useMutation({
    mutationFn: async (payload: { subject: string | null; body_content: string | null }) => {
      const { error } = await supabase
        .from('suggested_emails')
        .update({ subject: payload.subject, body_content: payload.body_content })
        .eq('id', email.id)
      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggested-emails'] })
      onSaved()
    },
  })

  const allListings = listings ?? []
  const active = allListings.filter((l) => (l.status ?? '').toLowerCase() === 'active')
  const pendingContingent = allListings.filter((l) => {
    const s = (l.status ?? '').toLowerCase()
    return s === 'pending' || s === 'contingent'
  })
  const other = allListings.filter((l) => {
    const s = (l.status ?? '').toLowerCase()
    return s !== 'active' && s !== 'pending' && s !== 'contingent'
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="email-modal-title"
    >
      <div
        className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-panel-hover"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-[#e5e7eb] bg-[#f9fafb] px-6 py-3.5">
          <div>
            <h2
              id="email-modal-title"
              className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1d21]"
            >
              Email to broker
            </h2>
            <p className="mt-0.5 text-[12px] text-[#6b7280]">
              {broker?.name ?? '(no name)'} · {broker?.email ?? '(no email)'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex rounded-full bg-[#e0f2fe] px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-[#0369a1]">
              {email.status}
            </span>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-[#6b7280] transition-colors hover:bg-[#e5e7eb] hover:text-[#1a1d21]"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="max-h-[calc(90vh-56px)] overflow-auto px-6 py-5 text-sm">
          <div className="grid h-full gap-6 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <section className="rounded-xl border border-[#e5e7eb] bg-[#f9fafb] px-4 py-3">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[#6b7280]">
                  Recipient
                </h3>
                <p className="mt-1.5 text-[13px] font-medium text-[#1a1d21]">
                  {broker?.name ?? '(no name)'}
                </p>
                <p className="text-[13px] text-[#374151]">
                  {broker?.email ?? '(no email)'}
                </p>
                {broker?.brokerage_name && (
                  <p className="mt-0.5 text-[12px] text-[#6b7280]">{broker.brokerage_name}</p>
                )}
              </section>

              <section className="flex flex-1 flex-col rounded-xl border border-[#e5e7eb] bg-white px-4 py-3">
                <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#6b7280]">
                  Edit email
                </h3>
                <label className="block text-[12px] text-[#6b7280]">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[#e5e7eb] bg-[#f9fafb] px-3 py-2 text-[13px] text-[#1a1d21] focus:border-[#1a1d21] focus:outline-none focus:ring-1 focus:ring-[#1a1d21]"
                  placeholder="Subject"
                />
                <label className="mt-3 block text-[12px] text-[#6b7280]">Body</label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={12}
                  className="mt-1 w-full flex-1 resize-none rounded-lg border border-[#e5e7eb] bg-[#f9fafb] px-3 py-2 text-[13px] leading-relaxed text-[#1a1d21] focus:border-[#1a1d21] focus:outline-none focus:ring-1 focus:ring-[#1a1d21]"
                  placeholder="Email body"
                />
                <div className="mt-3 flex gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => updateMutation.mutate({ subject: subject || null, body_content: body || null })}
                    disabled={
                      updateMutation.isPending ||
                      (subject === (email.subject ?? '') && body === (email.body_content ?? ''))
                    }
                    className="inline-flex flex-1 items-center justify-center rounded-lg bg-[#1a1d21] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#111827] disabled:opacity-50"
                  >
                    {updateMutation.isPending ? 'Saving…' : 'Save changes'}
                  </button>
                  {updateMutation.isError && (
                    <p className="text-[12px] text-[#dc2626]">
                      {updateMutation.error instanceof Error ? updateMutation.error.message : 'Save failed'}
                    </p>
                  )}
                </div>
              </section>
            </div>

            <section className="flex min-h-0 flex-col rounded-xl border border-[#e5e7eb] bg-[#f9fafb] px-4 py-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[#6b7280]">
                  Related listings
                </h3>
                {!listingsLoading && allListings.length > 0 && (
                  <span className="text-[11px] text-[#6b7280]">{allListings.length} total</span>
                )}
              </div>
              <div className="mt-1 min-h-0 flex-1 overflow-auto">
                {listingsLoading ? (
                  <p className="text-[12px] text-[#6b7280]">Loading listings…</p>
                ) : allListings.length === 0 ? (
                  <p className="text-[12px] text-[#6b7280]">No related listings for this broker.</p>
                ) : (
                  <div className="space-y-4 pb-1">
                    {active.length > 0 && (
                      <div>
                        <p className="mb-1.5 text-[11px] font-medium text-[#6b7280]">Active</p>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {active.map((l) => (
                            <ListingCard key={l.id} listing={l} />
                          ))}
                        </div>
                      </div>
                    )}
                    {pendingContingent.length > 0 && (
                      <div>
                        <p className="mb-1.5 text-[11px] font-medium text-[#6b7280]">Pending / Contingent</p>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {pendingContingent.map((l) => (
                            <ListingCard key={l.id} listing={l} variant="pending" />
                          ))}
                        </div>
                      </div>
                    )}
                    {other.length > 0 && (
                      <div>
                        <p className="mb-1.5 text-[11px] font-medium text-[#6b7280]">Other</p>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {other.map((l) => (
                            <ListingCard key={l.id} listing={l} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}

function OutLinkIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
  )
}

function ListingCard({
  listing,
  variant = 'default',
}: {
  listing: ListingSummary
  variant?: 'default' | 'pending'
}) {
  const hasLink = Boolean(listing.source_url && listing.source_url.startsWith('http'))
  return (
    <article
      className={`relative rounded-lg border px-3 py-2.5 ${
        variant === 'pending'
          ? 'border-emerald-200 bg-emerald-50'
          : 'border-[#e5e7eb] bg-[#f9fafb]'
      }`}
    >
      <div className="absolute right-2 top-2">
        {hasLink ? (
          <a
            href={listing.source_url!}
            target="_blank"
            rel="noreferrer"
            className="inline-flex rounded p-1 text-[#6b7280] hover:bg-[#e5e7eb] hover:text-sky-600"
            title="Open listing source in new tab"
            aria-label="Open listing source in new tab"
          >
            <OutLinkIcon />
          </a>
        ) : (
          <span className="inline-flex rounded p-1 text-[#d1d5db]" title="No source link for this listing">
            <OutLinkIcon />
          </span>
        )}
      </div>
      <p className="pr-8 text-[11px] font-semibold text-[#1a1d21]">
        {listing.address ?? '(no address)'}
      </p>
      <p className="mt-0.5 text-[10px] text-[#6b7280]">
        {[listing.city, listing.state, listing.zip].filter(Boolean).join(', ')}
      </p>
      <p className="mt-1 text-[11px] text-[#1a1d21]">
        {typeof listing.price === 'number'
          ? listing.price.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
          : 'Price N/A'}
      </p>
      <p className="mt-0.5 text-[10px] text-[#6b7280]">
        Status: {listing.status ?? '—'}
        {listing.sale_date && ` · ${new Date(listing.sale_date).toLocaleDateString()}`}
      </p>
      <div className="mt-1 flex items-center gap-1.5">
        {hasLink ? (
          <a
            href={listing.source_url!}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-[10px] font-medium text-sky-600 hover:underline"
            title="Open listing source in new tab"
          >
            <OutLinkIcon className="h-3.5 w-3.5" />
            Open source
          </a>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[10px] text-[#9ca3af]">
            <OutLinkIcon className="h-3.5 w-3.5" />
            No source link
          </span>
        )}
      </div>
    </article>
  )
}
