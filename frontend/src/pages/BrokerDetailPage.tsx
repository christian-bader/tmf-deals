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
    return <p className="text-[13px] text-[#6b7280]">No broker selected.</p>
  }

  if (isLoading) {
    return <p className="text-[13px] text-[#6b7280]">Loading broker…</p>
  }

  if (isError) {
    return (
      <p className="text-[13px] text-[#dc2626]">
        Failed to load broker: {(error as Error).message}
      </p>
    )
  }

  if (!data?.broker) {
    return (
      <p className="text-[13px] text-[#6b7280]">
        Broker not found or missing in Supabase.
      </p>
    )
  }

  const { broker, emails } = data

  return (
    <div className="flex h-full flex-col gap-5">
      <div>
        <h2 className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
          {broker.name ?? 'Unnamed broker'}
        </h2>
        <p className="mt-0.5 text-[13px] text-[#6b7280]">
          {broker.brokerage_name ?? 'No brokerage on file'}
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[#e5e7eb] bg-white p-4 shadow-panel">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[#6b7280]">
            Contact
          </h3>
          <dl className="mt-3 space-y-2">
            <InfoRow label="Email" value={broker.email ?? '—'} />
            <InfoRow label="Phone" value={broker.phone ?? '—'} />
            <InfoRow label="License" value={broker.license_number ?? '—'} />
            <InfoRow label="Licensed State" value={broker.state_licensed ?? '—'} />
          </dl>
        </div>

        <div className="rounded-xl border border-[#e5e7eb] bg-white p-4 shadow-panel">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[#6b7280]">
            Outreach history
          </h3>
          {emails.length === 0 ? (
            <p className="mt-3 text-[13px] text-[#6b7280]">
              No emails logged for this broker yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {emails.map((e) => (
                <li
                  key={e.id}
                  className="rounded-lg border border-[#e5e7eb] bg-[#f9fafb] p-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-[#6b7280]">
                      {new Date(e.time_sent).toLocaleString()}
                    </span>
                    <span className="text-[11px] font-medium uppercase tracking-wider text-[#374151]">
                      {e.send_status}
                    </span>
                  </div>
                  {e.body_snapshot && (
                    <p className="mt-1 line-clamp-2 text-[12px] text-[#374151]">
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
      <dt className="text-[12px] text-[#6b7280]">{label}</dt>
      <dd className="text-[12px] text-[#1a1d21]">{value}</dd>
    </div>
  )
}

