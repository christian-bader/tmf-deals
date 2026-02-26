import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient.ts'

type CountResult = { count: number | null }

type Counts = {
  potentialOutreaches: number
  listingsBeingAssessed: number
}

async function fetchCounts(): Promise<Counts> {
  const [{ count: outreachCount }, { data: emails, error: emailsError }] =
    await Promise.all([
      supabase
        .from('outreach_opportunities')
        .select('*', { count: 'exact', head: true }) as Promise<
        CountResult & { error: unknown }
      >,
      supabase
        .from('suggested_emails')
        .select('new_listing_ids,status'),
    ])

  if (emailsError) throw emailsError

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
    potentialOutreaches: outreachCount ?? 0,
    listingsBeingAssessed: listingIdSet.size,
  }
}

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard-counts'],
    queryFn: fetchCounts,
  })

  return (
    <div className="flex h-full flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-500">
          Snapshot of who you can reach out to and the listings they&apos;re
          attached to.
        </p>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading counts…</p>}
      {isError && (
        <p className="text-sm text-rose-500">
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
    <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm transition-transform duration-150 hover:-translate-y-0.5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

