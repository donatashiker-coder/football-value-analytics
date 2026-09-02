interface Tab {
  key: string
  label: string
  count?: number
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (key: string) => void
}

export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
      {tabs.map((t) => {
        const isActive = t.key === active
        return (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={isActive}
            className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${
              isActive
                ? 'border-teal-700 font-semibold text-teal-800 dark:border-teal-400 dark:text-teal-200'
                : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'
            }`}
            onClick={() => onChange(t.key)}
          >
            {t.label}
            {typeof t.count === 'number' && <span className="ml-1 text-xs muted">({t.count})</span>}
          </button>
        )
      })}
    </div>
  )
}
