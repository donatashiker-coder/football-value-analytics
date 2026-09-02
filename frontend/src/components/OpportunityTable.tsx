import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Opportunity } from '@/types'
import { localDateTime, odds, pct, signedPct } from '@/utils/format'
import { DataTable, type Column } from './DataTable'
import { StatusBadge, ValueBadge } from './Badges'
import { OpportunityDetails } from './OpportunityDetails'
import { PaperBetModal } from './PaperBetModal'
import { DemoBadge } from './DemoBanner'

interface Props {
  opportunities: Opportunity[]
  showMatch?: boolean
  compact?: boolean
  emptyMessage?: string
  maxRows?: number
  defaultSort?: { key: string; dir: 'asc' | 'desc' }
  /** Enables the record paper bet action. */
  allowBet?: boolean
}

function scoreCell(v: number | null | undefined) {
  if (v === null || v === undefined) return <span className="chip chip-grey">N/A</span>
  const cls = v >= 70 ? 'text-emerald-700 dark:text-emerald-300' : v >= 45 ? 'text-amber-700 dark:text-amber-300' : 'text-red-700 dark:text-red-300'
  return <span className={`font-medium num ${cls}`}>{Math.round(v)}</span>
}

function evCell(v: number | null | undefined) {
  if (v === null || v === undefined) return <span className="chip chip-grey">N/A</span>
  const cls = v >= 0.02 ? 'text-emerald-700 dark:text-emerald-300' : v >= 0 ? 'text-amber-700 dark:text-amber-300' : 'text-red-700 dark:text-red-300'
  return <span className={`font-medium num ${cls}`}>{signedPct(v)}</span>
}

export function OpportunityTable({
  opportunities,
  showMatch = true,
  compact = false,
  emptyMessage = 'No opportunities.',
  maxRows,
  defaultSort = { key: 'value_score', dir: 'desc' },
  allowBet = true,
}: Props) {
  const [betFor, setBetFor] = useState<Opportunity | null>(null)

  const columns: Column<Opportunity>[] = []
  if (showMatch) {
    columns.push({
      key: 'match',
      header: 'Match',
      sortValue: (o) => o.home_team,
      render: (o) => (
        <div className="min-w-[10rem]">
          <Link to={`/matches/${o.fixture_id}`} className="font-medium">
            {o.home_team} vs {o.away_team}
          </Link>
          <div className="text-xs muted">
            {o.competition} <DemoBadge show={o.is_demo} />
          </div>
        </div>
      ),
    })
  }
  columns.push(
    {
      key: 'market',
      header: 'Market',
      sortValue: (o) => o.market,
      render: (o) => (
        <div>
          <div>{o.market}</div>
          <div className="text-xs muted">{o.market_group}</div>
        </div>
      ),
    },
    { key: 'selection', header: 'Selection', sortValue: (o) => o.selection, render: (o) => <span className="whitespace-nowrap">{o.selection}{o.line !== null ? ` ${o.line}` : ''}</span> },
    {
      key: 'best_odds',
      header: 'Best odds',
      align: 'right',
      sortValue: (o) => o.best_odds,
      render: (o) => (o.best_odds === null ? <span className="chip chip-grey">N/A</span> : <span className="font-medium">{odds(o.best_odds)}</span>),
    },
    { key: 'bookmaker', header: 'Bookmaker', sortValue: (o) => o.best_bookmaker, render: (o) => o.best_bookmaker ?? <span className="muted">—</span> },
    { key: 'model_p', header: 'Model %', align: 'right', sortValue: (o) => o.model_probability, render: (o) => pct(o.model_probability) },
    { key: 'market_p', header: 'Market %', align: 'right', sortValue: (o) => o.market_probability, render: (o) => (o.market_probability === null ? <span className="chip chip-grey">N/A</span> : pct(o.market_probability)) },
    { key: 'fair_odds', header: 'Fair odds', align: 'right', sortValue: (o) => o.fair_odds, render: (o) => odds(o.fair_odds) },
    { key: 'ev', header: 'EV', align: 'right', sortValue: (o) => o.expected_value, render: (o) => evCell(o.expected_value) },
    { key: 'edge', header: 'Edge', align: 'right', sortValue: (o) => o.edge, render: (o) => (o.edge === null ? <span className="chip chip-grey">N/A</span> : signedPct(o.edge)) },
    { key: 'value_score', header: 'Value', align: 'right', sortValue: (o) => o.value_score, render: (o) => scoreCell(o.value_score) },
    { key: 'confidence', header: 'Conf.', align: 'right', sortValue: (o) => o.confidence, render: (o) => scoreCell(o.confidence) },
    { key: 'data_quality', header: 'Data Q', align: 'right', sortValue: (o) => o.data_quality, render: (o) => scoreCell(o.data_quality) },
  )
  if (!compact) {
    columns.push({ key: 'kickoff', header: 'Kickoff', sortValue: (o) => o.kickoff_utc, render: (o) => <span className="whitespace-nowrap text-xs">{localDateTime(o.kickoff_utc)}</span> })
  }
  columns.push({
    key: 'status',
    header: 'Status',
    sortValue: (o) => o.status,
    render: (o) => (
      <div className="flex flex-col gap-0.5">
        <StatusBadge status={o.status} />
        <ValueBadge label={o.value_label} />
      </div>
    ),
  })

  return (
    <>
      <DataTable
        columns={columns}
        rows={opportunities}
        rowKey={(o) => o.id}
        defaultSort={defaultSort}
        emptyMessage={emptyMessage}
        maxRows={maxRows}
        dense={compact}
        expand={(o) => <OpportunityDetails opp={o} onRecordBet={allowBet ? setBetFor : undefined} showMatchLink={showMatch} />}
      />
      {betFor && <PaperBetModal opportunity={betFor} open onClose={() => setBetFor(null)} />}
    </>
  )
}
