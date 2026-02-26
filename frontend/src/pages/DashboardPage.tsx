import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient.ts'

type Counts = {
  potentialOutreaches: number
  listingsBeingAssessed: number
}

async function fetchCounts(): Promise<Counts> {
  const [outreachRes, { data: emails, error: emailsError }] = await Promise.all([
    supabase
      .from('outreach_opportunities')
      .select('*', { count: 'exact', head: true }),
    supabase.from('suggested_emails').select('new_listing_ids,status'),
  ])

  if (emailsError) throw emailsError

  const outreachCount =
    outreachRes && 'count' in outreachRes ? (outreachRes as { count: number | null }).count : null

  const listingIdSet = new Set<string>()
  ;(emails ?? []).forEach((e) => {
    const ids = (e as { new_listing_ids: string[] | null }).new_listing_ids
    if (Array.isArray(ids)) {
      ids.forEach((id) => {
        if (id) listingIdSet.add(id)
      })
    }
  })

  return {
    potentialOutreaches: outreachCount != null ? outreachCount : 0,
    listingsBeingAssessed: listingIdSet.size,
  }
}

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard-counts'],
    queryFn: fetchCounts,
  })

  return (
    <div className="flex h-full flex-col gap-5">
      <div>
        <h2 className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
          Dashboard
        </h2>
        <p className="mt-0.5 text-[13px] text-[#6b7280]">
          Snapshot of who you can reach out to and the listings they&apos;re
          attached to.
        </p>
      </div>

      {isLoading && <p className="text-[13px] text-[#6b7280]">Loading…</p>}
      {isError && (
        <p className="text-[13px] text-[#dc2626]">
          Could not load counts. Check Supabase credentials.
        </p>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          <DashboardCard
            label="Potential outreaches"
            value={data.potentialOutreaches}
          />
          <DashboardCard
            label="Listings being assessed"
            value={data.listingsBeingAssessed}
          />
        </div>
      )}
    </div>
  )
}

function DashboardCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-[#e5e7eb] bg-white px-5 py-4 shadow-panel">
      <p className="text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
        {label}
      </p>
      <p className="mt-2.5 text-2xl font-semibold tracking-[-0.02em] text-[#1a1d21]">
        {value}
      </p>
    </div>
  )
}

