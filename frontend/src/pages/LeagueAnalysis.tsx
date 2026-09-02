import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useToast } from '@/hooks/useToast'
import type { League } from '@/types'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/States'
import { DemoBadge } from '@/components/DemoBanner'

export default function LeagueAnalysis() {
  const { data, loading, error, refetch } = useApi((signal) => api.leagues(signal), [])

  return (
    <div>
      <PageHeader title="League Analysis" subtitle="Enable or disable leagues and tune per-league model settings." />
      {loading && <LoadingState label="Loading leagues" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}
      {data && !loading && !error && (
        data.length === 0 ? (
          <EmptyState title="No leagues configured." />
        ) : (
          <div className="card">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>League</th>
                    <th>Country</th>
                    <th className="text-right">Tier</th>
                    <th className="text-right">Fixtures</th>
                    <th className="text-right">Results</th>
                    <th>Enabled</th>
                    <th className="text-right">Min sample</th>
                    <th className="text-right">Reliability</th>
                    <th className="text-right">Home adv.</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.map((l) => (
                    <LeagueRow key={l.code} league={l} onSaved={refetch} />
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

function LeagueRow({ league, onSaved }: { league: League; onSaved: () => void }) {
  const toast = useToast()
  const [enabled, setEnabled] = useState(league.enabled)
  const [minSample, setMinSample] = useState(String(league.settings.min_sample_size ?? ''))
  const [reliability, setReliability] = useState(String(league.settings.reliability ?? ''))
  const [homeAdv, setHomeAdv] = useState(league.settings.home_advantage === null ? '' : String(league.settings.home_advantage))
  const [saving, setSaving] = useState(false)

  const homeAdvValue = homeAdv.trim() === '' ? null : Number(homeAdv)
  const dirty =
    enabled !== league.enabled ||
    Number(minSample) !== league.settings.min_sample_size ||
    Number(reliability) !== league.settings.reliability ||
    homeAdvValue !== league.settings.home_advantage

  async function save(patch?: { enabled: boolean }) {
    setSaving(true)
    try {
      await api.updateLeagueSettings(league.code, patch ?? {
        enabled,
        min_sample_size: Number(minSample),
        reliability: Number(reliability),
        ...(homeAdvValue !== null && Number.isFinite(homeAdvValue) ? { home_advantage: homeAdvValue } : {}),
      })
      toast.push('success', `${league.name} updated`)
      onSaved()
    } catch (err) {
      toast.push('error', 'Save failed', err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr>
      <td>
        <Link to={`/leagues/${league.code}`} className="font-medium">
          {league.name}
        </Link>
        <div className="text-xs muted">
          {league.code} <DemoBadge show={league.is_demo} />
        </div>
      </td>
      <td>{league.country ?? '—'}</td>
      <td className="text-right num">{league.tier ?? '—'}</td>
      <td className="text-right num">{league.fixtures}</td>
      <td className="text-right num">{league.results}</td>
      <td>
        <label className="inline-flex items-center gap-1 text-xs">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked)
              save({ enabled: e.target.checked })
            }}
            aria-label={`Enable ${league.name}`}
          />
          {enabled ? <span className="chip chip-green">ENABLED</span> : <span className="chip chip-grey">DISABLED</span>}
        </label>
      </td>
      <td className="text-right">
        <input type="number" className="input w-20 text-right" min={1} value={minSample} onChange={(e) => setMinSample(e.target.value)} aria-label="Minimum sample size" />
      </td>
      <td className="text-right">
        <input type="number" className="input w-20 text-right" step="0.05" min={0} max={1} value={reliability} onChange={(e) => setReliability(e.target.value)} aria-label="Reliability" />
      </td>
      <td className="text-right">
        <input type="number" className="input w-20 text-right" step="0.01" value={homeAdv} placeholder="global" onChange={(e) => setHomeAdv(e.target.value)} aria-label="Home advantage (blank = use global setting)" />
      </td>
      <td>
        <button type="button" className="btn-primary btn-sm" disabled={!dirty || saving} onClick={() => save()}>
          {saving && <Spinner />}
          Save
        </button>
      </td>
    </tr>
  )
}
