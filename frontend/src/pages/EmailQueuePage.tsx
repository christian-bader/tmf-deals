import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient.ts'

type SuggestedEmail = {
  id: string
  broker_id: string
  subject: string | null
  body_content: string | null
  status: string
  created_at: string
}

async function fetchSuggestedEmails() {
  const { data, error } = await supabase
    .from('suggested_emails')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(100)

  if (error) throw error
  return data as SuggestedEmail[]
}

export function EmailQueuePage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggested-emails'],
    queryFn: fetchSuggestedEmails,
  })

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

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Email Queue</h2>
          <p className="mt-1 text-sm text-slate-500">
            Review, edit, and approve LLM-generated outreach emails.
          </p>
        </div>
      </div>

      {data && (
        <div className="inline-flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 shadow-sm">
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

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {isError && (
        <p className="text-sm text-rose-500">
          Failed to load emails: {(error as Error).message}
        </p>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((email) => (
            <article
              key={email.id}
              className="flex flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {email.status}
                </span>
                <span className="text-xs text-slate-400">
                  {new Date(email.created_at).toLocaleString()}
                </span>
              </div>
              <h3 className="mt-2 text-sm font-semibold text-slate-900">
                {email.subject || '(no subject)'}
              </h3>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs text-slate-800">
                {email.body_content || '(no body)'}
              </pre>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  className="inline-flex flex-1 items-center justify-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                  disabled
                >
                  Approve (wired via Apps Script)
                </button>
                <button
                  type="button"
                  className="inline-flex flex-1 items-center justify-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  disabled
                >
                  Skip
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

