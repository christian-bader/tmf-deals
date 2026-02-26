import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient.ts'

type Broker = {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  brokerage_name: string | null
  license_number: string | null
  state_licensed: string | null
}

type SentEmailLog = {
  id: string
  time_sent: string
  send_status: string
  body_snapshot: string | null
}

async function fetchBroker(id: string) {
  const [{ data: broker }, { data: emails }] = await Promise.all([
    supabase.from('brokers').select('*').eq('id', id).maybeSingle(),
    supabase
      .from('sent_email_logs')
      .select('id,time_sent,send_status,body_snapshot')
      .eq('broker_id', id)
      .order('time_sent', { ascending: false })
      .limit(20),
  ])

  return { broker: broker as Broker | null, emails: (emails ?? []) as SentEmailLog[] }
}

export function BrokerDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['broker-detail', id],
    enabled: !!id,
    queryFn: () => fetchBroker(id!),
  })

  if (!id) {
    return <p className="text-sm text-slate-300">No broker selected.</p>
  }

  if (isLoading) {
    return <p className="text-sm text-slate-300">Loading broker…</p>
  }

  if (isError) {
    return (
      <p className="text-sm text-rose-400">
        Failed to load broker: {(error as Error).message}
      </p>
    )
  }

  if (!data?.broker) {
    return (
      <p className="text-sm text-slate-300">
        Broker not found or missing in Supabase.
      </p>
    )
  }

  const { broker, emails } = data

  return (
    <div className="flex h-full flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-50">
          {broker.name ?? 'Unnamed broker'}
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          {broker.brokerage_name ?? 'No brokerage on file'}
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Contact
          </h3>
          <dl className="mt-3 space-y-2">
            <InfoRow label="Email" value={broker.email ?? '—'} />
            <InfoRow label="Phone" value={broker.phone ?? '—'} />
            <InfoRow
              label="License"
              value={broker.license_number ?? '—'}
            />
            <InfoRow
              label="Licensed State"
              value={broker.state_licensed ?? '—'}
            />
          </dl>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Outreach history
          </h3>
          {emails.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">
              No emails logged for this broker yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {emails.map((e) => (
                <li
                  key={e.id}
                  className="rounded-md border border-slate-800 bg-slate-900/60 p-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-slate-400">
                      {new Date(e.time_sent).toLocaleString()}
                    </span>
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-300">
                      {e.send_status}
                    </span>
                  </div>
                  {e.body_snapshot && (
                    <p className="mt-1 line-clamp-2 text-xs text-slate-300">
                      {e.body_snapshot}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-xs text-slate-100">{value}</dd>
    </div>
  )
}

