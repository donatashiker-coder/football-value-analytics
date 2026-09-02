import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { PageHeader } from '@/components/PageHeader'
import { OpportunityTable } from '@/components/OpportunityTable'
import { ValueFilters, defaultFilters, filtersToQuery } from '@/components/ValueFilters'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'

export default function ValueBets() {
  const [params] = useSearchParams()
  const [filters, setFilters] = useState(() => defaultFilters({ market_group: params.get('market_group') ?? '' }))
  const query = filtersToQuery(filters, { limit: 500 })
  const { data, loading, error, refetch } = useApi((signal) => api.value(query, signal), [JSON.stringify(query)])

  return (
    <div>
      <PageHeader
        title="Value Bets"
        subtitle={data ? `${data.count} opportunities · ${data.date ?? filters.day}${filters.days > 1 ? ` +${filters.days - 1}d` : ''}` : undefined}
        actions={
          <>
            <a className="btn-secondary btn-sm" href={api.valueExportUrl({ day: filters.day, days: filters.days, fmt: 'csv' })} download>
              Export CSV
            </a>
            <a className="btn-secondary btn-sm" href={api.valueExportUrl({ day: filters.day, days: filters.days, fmt: 'json' })} target="_blank" rel="noreferrer">
              Export JSON
            </a>
          </>
        }
      />
      <div className="space-y-4">
        <ValueFilters value={filters} onChange={setFilters} />
        {loading && <LoadingState label="Loading opportunities" />}
        {error && !loading && <ErrorState message={error} onRetry={refetch} />}
        {data && !loading && !error && (
          data.opportunities.length === 0 ? (
            <EmptyState title="No opportunities match these filters.">
              {filters.status === 'VALUE_CANDIDATE' ? 'Switch status to “All” to see NO BET and ODDS UNAVAILABLE rows and their reasons.' : 'Try another date range or run a scan from the Dashboard.'}
            </EmptyState>
          ) : (
            <div className="card">
              <OpportunityTable opportunities={data.opportunities} />
              {data.disclaimer && <p className="mt-3 text-xs muted">{data.disclaimer}</p>}
            </div>
          )
        )}
      </div>
    </div>
  )
}
