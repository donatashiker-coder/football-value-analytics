import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'
import { DemoBadge } from '@/components/DemoBanner'

export default function TeamAnalysis() {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [competition, setCompetition] = useState('')
  const leagues = useApi((signal) => api.leagues(signal), [])

  useEffect(() => {
    const t = window.setTimeout(() => setQ(input.trim()), 300)
    return () => window.clearTimeout(t)
  }, [input])

  const { data, loading, error, refetch } = useApi((signal) => api.teams({ q: q || undefined, competition: competition || undefined, limit: 100 }, signal), [q, competition])

  return (
    <div>
      <PageHeader title="Team Analysis" subtitle="Search a team to open its statistics, form and news." />
      <div className="card mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="md:col-span-2">
          <label className="label" htmlFor="team-q">
            Team name
          </label>
          <input id="team-q" className="input" placeholder="Start typing a team name..." value={input} onChange={(e) => setInput(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="team-league">
            League
          </label>
          <select id="team-league" className="input" value={competition} onChange={(e) => setCompetition(e.target.value)}>
            <option value="">All leagues</option>
            {(leagues.data ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      {loading && <LoadingState label="Searching teams" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}
      {data && !loading && !error && (
        data.length === 0 ? (
          <EmptyState title="No teams found." />
        ) : (
          <div className="card">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Team</th>
                    <th>Short name</th>
                    <th>Country</th>
                    <th>Competition</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <Link to={`/teams/${t.id}`} className="font-medium">
                          {t.name}
                        </Link>{' '}
                        <DemoBadge show={t.is_demo} />
                      </td>
                      <td>{t.short_name ?? '—'}</td>
                      <td>{t.country ?? '—'}</td>
                      <td>{leagues.data?.find((l) => l.id === t.competition_id)?.name ?? (t.competition_id ?? '—')}</td>
                      <td>
                        <Link to={`/teams/${t.id}`} className="btn-secondary btn-sm">
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}
    </div>
  )
}
