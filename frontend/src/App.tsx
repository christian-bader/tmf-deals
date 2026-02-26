import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'

const navLinkBase = 'rounded-lg px-3 py-2 text-sm font-medium transition-colors'

const navItems = [
  { to: '/', end: true, label: 'Dashboard', short: 'D' },
  { to: '/opportunities', end: false, label: 'Outreach Opportunities', short: 'O' },
  { to: '/emails', end: false, label: 'Email Queue', short: 'E' },
  { to: '/listings', end: false, label: 'Listings', short: 'L' },
] as const

function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-6">
        <header className="mb-6 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">
              TMF Deals Outreach
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Broker opportunities, email queue, and listings from Supabase.
            </p>
          </div>
          <div className="rounded-full border border-slate-200 bg-white/80 px-4 py-1 text-xs text-slate-500 shadow-sm">
            Supabase + Gmail · Trinity Mortgage Fund
          </div>
        </header>

        <div className="flex flex-1 gap-6">
          <aside
            className={`shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm transition-[width] duration-200 ${
              sidebarCollapsed ? 'w-[52px]' : 'w-60'
            }`}
          >
            <nav className="flex flex-col gap-1 text-sm">
              {navItems.map(({ to, end, label, short }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  title={sidebarCollapsed ? label : undefined}
                  className={({ isActive }) =>
                    `${navLinkBase} flex items-center ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`
                  }
                >
                  {sidebarCollapsed ? (
                    <span className="truncate">{short}</span>
                  ) : (
                    <span>{label}</span>
                  )}
                </NavLink>
              ))}
            </nav>
            <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              className="mt-3 flex w-full items-center justify-center rounded-lg py-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
              title={sidebarCollapsed ? 'Expand menu' : 'Collapse menu'}
            >
              {sidebarCollapsed ? (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              )}
            </button>
          </aside>

          <main className="flex-1 min-w-0">
            <div className="h-full rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

export default App
