import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { hours, localDateTime } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState, WarningBox } from '@/components/States'
import { FreshnessChip } from '@/components/FreshnessChip'

export default function DataSourcesPage() {
  const sources = useApi((signal) => api.dataSources(signal), [])
  const health = useApi((signal) => api.dataHealth(signal), [])
  const sys = useApi((signal) => api.health(signal), [])

  return (
    <div>
      <PageHeader title="Data Sources" subtitle="Providers, configuration status and data freshness." />
      <div className="space-y-4">
        {sources.loading && <LoadingState label="Loading data sources" />}
        {sources.error && <ErrorState message={sources.error} onRetry={sources.refetch} />}
        {sources.data && (
          <>
            {sources.data.message && <WarningBox title={sources.data.mode.toUpperCase()}>{sources.data.message}</WarningBox>}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {sources.data.providers.map((p) => (
                <div key={p.key} className="card">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-xs muted">
                        {p.key} · {p.role}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      {p.configured ? <span className="chip chip-green">CONFIGURED</span> : <span className="chip chip-grey">NOT CONFIGURED</span>}
                      {p.active ? <span className="chip chip-green">ACTIVE</span> : <span className="chip chip-yellow">INACTIVE</span>}
                    </div>
                  </div>
                  {p.fields.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {p.fields.map((f) => (
                        <span key={f} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] dark:bg-slate-800">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                  {p.notes && <p className="mt-2 text-xs muted">{p.notes}</p>}
                </div>
              ))}
            </div>
          </>
        )}

        <Section title="Data health">
          {health.loading && <LoadingState label="Loading data health" />}
          {health.error && <ErrorState message={health.error} onRetry={health.refetch} />}
          {health.data && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`chip ${health.data.status === 'ok' ? 'chip-green' : 'chip-yellow'}`}>{health.data.status.toUpperCase()}</span>
                <FreshnessChip hoursOld={health.data.odds_age_hours} />
                <span className="muted">Last odds update: {health.data.last_odds_update ? localDateTime(health.data.last_odds_update) : 'never'} ({hours(health.data.odds_age_hours)} ago)</span>
                <span className="muted">Last fixture update: {health.data.last_fixture_update ? localDateTime(health.data.last_fixture_update) : 'never'}</span>
                {sys.data && (
                  <span className="muted">
                    API v{sys.data.version} · db: {sys.data.database} · server time {localDateTime(sys.data.time_utc)}
                  </span>
                )}
              </div>
              {health.data.warnings.length > 0 && (
                <WarningBox title="Warnings">
                  <ul className="list-inside list-disc text-xs">
                    {health.data.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </WarningBox>
              )}
              <div>
                <div className="mb-1 text-xs font-semibold uppercase muted">API requests (last 24h)</div>
                {health.data.api_requests_24h.length === 0 ? (
                  <div className="text-xs muted">No provider requests recorded.</div>
                ) : (
                  <table className="table text-xs">
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th className="text-right">Requests</th>
                        <th className="text-right">Cached</th>
                        <th className="text-right">Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {health.data.api_requests_24h.map((r) => (
                        <tr key={r.provider}>
                          <td>{r.provider}</td>
                          <td className="text-right num">{r.requests}</td>
                          <td className="text-right num">{r.cached}</td>
                          <td className={`text-right num ${r.errors > 0 ? 'text-red-700 dark:text-red-300' : ''}`}>{r.errors}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </Section>

        {sources.data && (
          <Section title="League to provider identifiers">
            {sources.data.leagues.length === 0 ? (
              <EmptyState title="No leagues configured." />
            ) : (
              <div className="table-wrap">
                <table className="table text-xs">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>League</th>
                      <th>Country</th>
                      <th>API-Football</th>
                      <th>football-data</th>
                      <th>The Odds API</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.data.leagues.map((l) => (
                      <tr key={l.code}>
                        <td className="font-mono">{l.code}</td>
                        <td>{l.name}</td>
                        <td>{l.country ?? '—'}</td>
                        <td>{l.api_football ?? <span className="muted">—</span>}</td>
                        <td>{l.football_data ?? <span className="muted">—</span>}</td>
                        <td>{l.the_odds_api ?? <span className="muted">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        )}
      </div>
    </div>
  )
}
