import { NavLink } from 'react-router-dom'

const NAV: { to: string; label: string; end?: boolean }[] = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/matches', label: "Today's Matches" },
  { to: '/value', label: 'Value Bets' },
  { to: '/goals', label: 'Goals' },
  { to: '/corners', label: 'Corners' },
  { to: '/low-scoring', label: 'Low Scoring' },
  { to: '/teams', label: 'Team Analysis' },
  { to: '/leagues', label: 'League Analysis' },
  { to: '/odds', label: 'Odds' },
  { to: '/backtests', label: 'Backtesting' },
  { to: '/paper-bets', label: 'Paper Bets' },
  { to: '/bankroll', label: 'Bankroll' },
  { to: '/performance', label: 'Model Performance' },
  { to: '/settings', label: 'Settings' },
  { to: '/data-sources', label: 'Data Sources' },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-56 transform border-r border-slate-200 bg-white transition-transform dark:border-slate-800 dark:bg-slate-900 md:static md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Main navigation"
      >
        <div className="flex h-14 items-center border-b border-slate-200 px-4 dark:border-slate-800">
          <NavLink to="/" className="flex items-center gap-2 text-slate-900 no-underline hover:no-underline dark:text-slate-100" onClick={onClose}>
            <span className="inline-flex h-7 w-7 items-center justify-center rounded bg-teal-700 text-xs font-bold text-white">FV</span>
            <span className="text-sm font-semibold leading-tight">
              Football Value
              <br />
              Analytics
            </span>
          </NavLink>
        </div>
        <nav className="flex flex-col gap-0.5 p-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 text-sm no-underline hover:no-underline ${
                  isActive
                    ? 'bg-teal-50 font-semibold text-teal-800 dark:bg-teal-900/40 dark:text-teal-200'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
