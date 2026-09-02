import { useState } from 'react'
import type { ValueQuery } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { OpportunityList } from '@/types'
import { PageHeader } from './PageHeader'
import { OpportunityTable } from './OpportunityTable'
import { ScannerPanel } from './ScannerPanel'
import { ValueFilters, defaultFilters, filtersToQuery } from './ValueFilters'
import { EmptyState, ErrorState, LoadingState } from './States'

interface Props {
  title: string
  subtitle?: string
  fetcher: (params: ValueQuery, signal: AbortSignal) => Promise<OpportunityList>
  scannerKind: 'high_scoring' | 'low_scoring' | 'high_corners'
}

/**
 * Shared page for Goals / Corners / Low Scoring: filters + opportunity table + expected-totals scanner.
 * The endpoints are already scoped to their market groups, so no market_group filter is sent.
 */
export function OpportunityListPage({ title, subtitle, fetcher, scannerKind }: Props) {
  const [filters, setFilters] = useState(() => defaultFilters())
  const query = filtersToQuery(filters, { limit: 500 })
  const { data, loading, error, refetch } = useApi((signal) => fetcher(query, signal), [JSON.stringify(query)])

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle ?? (data ? `${data.count} opportunities` : undefined)} />
      <div className="space-y-4">
        <ValueFilters value={filters} onChange={setFilters} fixedGroup />
        {loading && <LoadingState label="Loading opportunities" />}
        {error && !loading && <ErrorState message={error} onRetry={refetch} />}
        {data && !loading && !error && (
          data.opportunities.length === 0 ? (
            <EmptyState title="No opportunities match these filters.">
              {filters.status === 'VALUE_CANDIDATE' ? 'Switch status to “All” to see NO BET and ODDS UNAVAILABLE rows with their reasons.' : 'Try a wider date range.'}
            </EmptyState>
          ) : (
            <div className="card">
              <OpportunityTable opportunities={data.opportunities} />
            </div>
          )
        )}
        <ScannerPanel kind={scannerKind} day={filters.day} days={filters.days} />
      </div>
    </div>
  )
}
