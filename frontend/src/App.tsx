import { Outlet, NavLink } from 'react-router-dom'
import { PageErrorBoundary } from './PageErrorBoundary'
import { ScrapeConfigButton } from './components/ScrapeConfigButton'

const navItems = [
  { to: '/', end: true, label: 'Dashboard' },
  { to: '/opportunities', end: false, label: 'Outreach Opportunities' },
  { to: '/emails', end: false, label: 'Email Queue' },
  { to: '/listings', end: false, label: 'Listings' },
] as const

function TrinityLogo() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1a1d21] text-[13px] font-bold tracking-tight text-white">
        T
      </div>
      <span className="text-[1.125rem] font-semibold tracking-[-0.02em] text-[#1a1d21]">
        Trinity Mortgage Fund
      </span>
    </div>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-[#f8f9fa]">
      <header className="sticky top-0 z-40 border-b border-[#e5e7eb] bg-white shadow-sm">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-5">
          <div className="flex items-center gap-8">
            <TrinityLogo />
            <nav className="flex items-center gap-1">
              {navItems.map(({ to, end, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-[#1a1d21] text-white'
                        : 'text-[#374151] hover:bg-[#f3f4f6]'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <ScrapeConfigButton />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-5">
        <main>
          <div className="min-h-[calc(100vh-6rem)] rounded-xl border border-[#e5e7eb] bg-white p-5 shadow-panel">
            <PageErrorBoundary>
              <Outlet />
            </PageErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
