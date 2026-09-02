import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Opportunity } from '@/types'
import { api } from '@/services/api'
import { localDateTime, odds, pct, score, signedPct } from '@/utils/format'
import { EvBadge, ScoreChip, StatusBadge, ValueBadge } from './Badges'
import { ProbabilityBar } from './ProbabilityBar'
import { FreshnessChip } from './FreshnessChip'
import { Spinner } from './States'
import { DemoBadge } from './DemoBanner'

interface Props {
  opp: Opportunity
  onRecordBet?: (opp: Opportunity) => void
  showMatchLink?: boolean
}

/** Expanded "why does this appear" panel for an opportunity. */
export function OpportunityDetails({ opp, onRecordBet, showMatchLink = true }: Props) {
  const [llm, setLlm] = useState<{ text: string; available: boolean } | null>(
    opp.llm_explanation ? { text: opp.llm_explanation, available: true } : null,
  )
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmError, setLlmError] = useState<string | null>(null)

  async function explain() {
    setLlmLoading(true)
    setLlmError(null)
    try {
      const r = await api.explain(opp.id)
      if (!r.llm_available) {
        setLlm({ text: r.explanation || 'LLM provider not configured.', available: false })
      } else {
        setLlm({ text: r.explanation || 'No explanation returned.', available: true })
      }
    } catch (err) {
      setLlmError(err instanceof Error ? err.message : 'Explain failed')
    } finally {
      setLlmLoading(false)
    }
  }

  const canBet = opp.status === 'VALUE_CANDIDATE' && opp.best_odds !== null

  return (
    <div className="grid gap-4 text-sm lg:grid-cols-3">
      <div className="space-y-2 lg:col-span-1">
        <div className="flex flex-wrap items-center gap-1">
          <StatusBadge status={opp.status} />
          <ValueBadge label={opp.value_label} />
          <EvBadge ev={opp.expected_value} />
          <DemoBadge show={opp.is_demo} />
        </div>
        <div className="flex flex-wrap gap-1">
          <ScoreChip label="Value" value={opp.value_score} />
          <ScoreChip label="Confidence" value={opp.confidence} />
          <ScoreChip label="Data quality" value={opp.data_quality} />
          <FreshnessChip recordedAt={opp.odds_recorded_at} />
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <Dt>Market</Dt>
          <Dd>
            {opp.market} — {opp.selection}
            {opp.line !== null ? ` (${opp.line})` : ''}
          </Dd>
          <Dt>Model probability</Dt>
          <Dd>{pct(opp.model_probability)}</Dd>
          <Dt>Market probability</Dt>
          <Dd>{pct(opp.market_probability)}</Dd>
          <Dt>Fair odds</Dt>
          <Dd>{odds(opp.fair_odds)}</Dd>
          <Dt>Best odds</Dt>
          <Dd>
            {odds(opp.best_odds)}
            {opp.best_bookmaker ? ` @ ${opp.best_bookmaker}` : ''}
          </Dd>
          <Dt>Median odds</Dt>
          <Dd>
            {odds(opp.median_odds)} ({opp.bookmaker_count} bookmakers)
          </Dd>
          <Dt>EV</Dt>
          <Dd>{signedPct(opp.expected_value)}</Dd>
          <Dt>Edge</Dt>
          <Dd>{signedPct(opp.edge)}</Dd>
          <Dt>Value score</Dt>
          <Dd>{score(opp.value_score)} / 100</Dd>
          <Dt>Model version</Dt>
          <Dd>{opp.model_version}</Dd>
          <Dt>Scan date</Dt>
          <Dd>{opp.scan_date}</Dd>
          <Dt>Kickoff</Dt>
          <Dd>{localDateTime(opp.kickoff_utc)}</Dd>
          {opp.movement && (
            <>
              <Dt>Odds movement</Dt>
              <Dd>
                {odds(opp.movement.opening)} → {odds(opp.movement.current)} ({opp.movement.direction}
                {opp.movement.movement_pct !== null ? `, ${signedPct(opp.movement.movement_pct)}` : ''})
              </Dd>
            </>
          )}
        </dl>
        <ProbabilityBar model={opp.model_probability} market={opp.market_probability} />
        <div className="flex flex-wrap gap-2 pt-1">
          {showMatchLink && (
            <Link className="btn-secondary btn-sm" to={`/matches/${opp.fixture_id}`}>
              Match page
            </Link>
          )}
          {onRecordBet && (
            <button type="button" className="btn-primary btn-sm" disabled={!canBet} onClick={() => onRecordBet(opp)} title={canBet ? '' : 'Only value candidates with odds can be recorded'}>
              Record paper bet
            </button>
          )}
          <button type="button" className="btn-secondary btn-sm" onClick={explain} disabled={llmLoading}>
            {llmLoading && <Spinner />}
            Explain (LLM)
          </button>
        </div>
      </div>

      <div className="space-y-3 lg:col-span-2">
        <div>
          <div className="text-xs font-semibold uppercase muted">Explanation</div>
          <p className="whitespace-pre-wrap">{opp.explanation || 'No explanation available.'}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <FactorList title="Key factors" items={opp.key_factors} tone="green" />
          <FactorList title="Risk factors" items={opp.risk_factors} tone="yellow" />
          <FactorList title="No-bet reasons" items={opp.no_bet_reasons} tone="red" emptyText={opp.status === 'VALUE_CANDIDATE' ? 'None — passes all filters' : 'None listed'} />
        </div>
        {(llm || llmError) && (
          <div className={`rounded border p-2 text-xs ${llm && !llm.available ? 'border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-800' : 'border-sky-200 bg-sky-50 dark:border-sky-900 dark:bg-sky-950/40'}`}>
            <div className="font-semibold uppercase muted">LLM explanation</div>
            {llmError ? <div className="text-red-700 dark:text-red-300">{llmError}</div> : <p className="whitespace-pre-wrap">{llm?.text}</p>}
            {llm && !llm.available && <div className="mt-1 muted">LLM provider not configured — showing the deterministic explanation only.</div>}
          </div>
        )}
      </div>
    </div>
  )
}

function Dt({ children }: { children: React.ReactNode }) {
  return <dt className="muted">{children}</dt>
}
function Dd({ children }: { children: React.ReactNode }) {
  return <dd className="num">{children}</dd>
}

function FactorList({ title, items, tone, emptyText = 'None listed' }: { title: string; items: string[]; tone: 'green' | 'yellow' | 'red'; emptyText?: string }) {
  const bullet = tone === 'green' ? 'text-emerald-600' : tone === 'yellow' ? 'text-amber-600' : 'text-red-600'
  return (
    <div>
      <div className="text-xs font-semibold uppercase muted">{title}</div>
      {items && items.length > 0 ? (
        <ul className="mt-1 space-y-0.5 text-xs">
          {items.map((it, i) => (
            <li key={i} className="flex gap-1">
              <span className={bullet} aria-hidden="true">
                •
              </span>
              <span>{it}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-1 text-xs muted">{emptyText}</div>
      )}
    </div>
  )
}
