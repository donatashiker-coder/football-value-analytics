import { useMemo, useState, type ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: ReactNode
  /** Value used for sorting; defaults to render output if primitive. */
  sortValue?: (row: T) => number | string | null | undefined
  render: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  className?: string
  sortable?: boolean
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  defaultSort?: { key: string; dir: 'asc' | 'desc' }
  /** Optional expandable content per row. */
  expand?: (row: T) => ReactNode
  emptyMessage?: string
  dense?: boolean
  rowClassName?: (row: T) => string
  maxRows?: number
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  defaultSort,
  expand,
  emptyMessage = 'No rows.',
  dense = false,
  rowClassName,
  maxRows,
}: Props<T>) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(defaultSort ?? null)
  const [expanded, setExpanded] = useState<Set<string | number>>(new Set())
  const [showAll, setShowAll] = useState(false)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col || !col.sortValue) return rows
    const getter = col.sortValue
    const copy = [...rows]
    copy.sort((a, b) => {
      const va = getter(a)
      const vb = getter(b)
      const na = va === null || va === undefined
      const nb = vb === null || vb === undefined
      if (na && nb) return 0
      if (na) return 1
      if (nb) return -1
      let cmp: number
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb
      else cmp = String(va).localeCompare(String(vb))
      return sort.dir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [rows, sort, columns])

  const visible = maxRows && !showAll ? sorted.slice(0, maxRows) : sorted

  function toggleSort(col: Column<T>) {
    if (!col.sortValue || col.sortable === false) return
    setSort((prev) => {
      if (!prev || prev.key !== col.key) return { key: col.key, dir: 'desc' }
      return { key: col.key, dir: prev.dir === 'desc' ? 'asc' : 'desc' }
    })
  }

  function toggleExpand(key: string | number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const colSpan = columns.length + (expand ? 1 : 0)

  return (
    <div className="table-wrap">
      <table className={`table ${dense ? 'text-xs' : ''}`}>
        <thead>
          <tr>
            {expand && <th className="w-8" aria-label="Expand" />}
            {columns.map((col) => {
              const sortable = Boolean(col.sortValue) && col.sortable !== false
              const active = sort?.key === col.key
              return (
                <th
                  key={col.key}
                  className={`${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''} ${col.className ?? ''}`}
                  aria-sort={active ? (sort?.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {sortable ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 uppercase hover:text-slate-900 dark:hover:text-slate-100"
                      onClick={() => toggleSort(col)}
                    >
                      {col.header}
                      <span aria-hidden="true" className={active ? '' : 'opacity-30'}>
                        {active && sort?.dir === 'asc' ? '▲' : '▼'}
                      </span>
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 && (
            <tr>
              <td colSpan={colSpan} className="py-6 text-center muted">
                {emptyMessage}
              </td>
            </tr>
          )}
          {visible.map((row) => {
            const key = rowKey(row)
            const isOpen = expanded.has(key)
            return (
              <RowGroup key={key}>
                <tr className={rowClassName ? rowClassName(row) : ''}>
                  {expand && (
                    <td>
                      <button
                        type="button"
                        className="btn-secondary btn-sm h-6 w-6 justify-center px-0"
                        aria-expanded={isOpen}
                        aria-label={isOpen ? 'Collapse row' : 'Expand row'}
                        onClick={() => toggleExpand(key)}
                      >
                        {isOpen ? '−' : '+'}
                      </button>
                    </td>
                  )}
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`${col.align === 'right' ? 'text-right num' : col.align === 'center' ? 'text-center' : ''} ${col.className ?? ''}`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
                {expand && isOpen && (
                  <tr className="bg-slate-50 dark:bg-slate-800/40">
                    <td colSpan={colSpan} className="p-3">
                      {expand(row)}
                    </td>
                  </tr>
                )}
              </RowGroup>
            )
          })}
        </tbody>
      </table>
      {maxRows && sorted.length > maxRows && (
        <div className="py-2 text-center">
          <button type="button" className="btn-secondary btn-sm" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show fewer' : `Show all ${sorted.length} rows`}
          </button>
        </div>
      )}
    </div>
  )
}

function RowGroup({ children }: { children: ReactNode }) {
  return <>{children}</>
}
