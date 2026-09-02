import type { ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="mt-0.5 text-sm muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Section({ title, children, actions, className = '' }: { title: string; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2>{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  )
}
