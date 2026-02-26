import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { PageErrorBoundary } from './PageErrorBoundary'

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
    <div className="min-h-screen bg-[#f8f9fa]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-5 py-5">
        <header className="mb-5 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-[1.25rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
              TMF Deals Outreach
            </h1>
            <p className="mt-0.5 text-[13px] text-[#6b7280]">
              Broker opportunities, email queue, and listings.
            </p>
          </div>
          <span className="text-[12px] text-[#6b7280]">
            Trinity Mortgage Fund
          </span>
        </header>

        <div className="flex flex-1 gap-5">
          <aside
            className={`shrink-0 overflow-hidden rounded-xl border border-[#e5e7eb] bg-white p-2.5 shadow-panel transition-[width] duration-200 ${
              sidebarCollapsed ? 'w-[52px]' : 'w-56'
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
                        ? 'bg-[#1a1d21] text-white'
                        : 'text-[#374151] hover:bg-[#f3f4f6]'
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
              className="mt-2 flex w-full items-center justify-center rounded-lg py-2 text-[#6b7280] transition-colors hover:bg-[#f3f4f6] hover:text-[#374151]"
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

          <main className="min-w-0 flex-1">
            <div className="h-full rounded-xl border border-[#e5e7eb] bg-white p-5 shadow-panel">
              <PageErrorBoundary>
                <Outlet />
              </PageErrorBoundary>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

export default App
