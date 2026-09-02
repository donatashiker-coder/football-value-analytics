import { useEffect, useState } from 'react'
import type { Opportunity, StakePreview } from '@/types'
import { api } from '@/services/api'
import { useToast } from '@/hooks/useToast'
import { money, odds as fmtOdds, pct, signedPct } from '@/utils/format'
import { Modal } from './Modal'
import { Spinner } from './States'

interface Props {
  opportunity: Opportunity
  open: boolean
  onClose: () => void
  onCreated?: () => void
}

const METHODS: { key: keyof StakePreview['stakes']; label: string }[] = [
  { key: 'flat', label: 'Flat' },
  { key: 'percentage', label: 'Percentage' },
  { key: 'quarter_kelly', label: 'Quarter Kelly' },
  { key: 'half_kelly', label: 'Half Kelly' },
  { key: 'full_kelly', label: 'Full Kelly' },
]

/** Modal for recording a paper bet from an opportunity, with a stake preview per staking method. */
export function PaperBetModal({ opportunity, open, onClose, onCreated }: Props) {
  const toast = useToast()
  const [odds, setOdds] = useState<string>(opportunity.best_odds !== null ? opportunity.best_odds.toFixed(2) : '')
  const [stake, setStake] = useState<string>('')
  const [method, setMethod] = useState<string>('')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<StakePreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const oddsNum = Number(odds)
  const oddsValid = Number.isFinite(oddsNum) && oddsNum > 1

  useEffect(() => {
    if (!open || !oddsValid) {
      setPreview(null)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api
        .stakePreview(opportunity.model_probability, oddsNum, controller.signal)
        .then((p) => {
          setPreview(p)
          setPreviewError(null)
          setMethod((m) => m || p.default_method)
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          setPreviewError(err instanceof Error ? err.message : 'Stake preview unavailable')
        })
    }, 200)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [open, oddsValid, oddsNum, opportunity.model_probability])

  useEffect(() => {
    if (!preview || !method) return
    const s = preview.stakes[method as keyof StakePreview['stakes']]
    if (typeof s === 'number') setStake(s.toFixed(2))
  }, [preview, method])

  async function submit() {
    setError(null)
    if (!oddsValid) {
      setError('Odds must be a number greater than 1.')
      return
    }
    const stakeNum = Number(stake)
    setSubmitting(true)
    try {
      await api.createPaperBet({
        fixture_id: opportunity.fixture_id,
        market_key: opportunity.market_key,
        selection: opportunity.selection,
        odds: oddsNum,
        stake: Number.isFinite(stakeNum) && stakeNum > 0 ? stakeNum : undefined,
        bookmaker_key: opportunity.best_bookmaker ?? undefined,
        opportunity_id: opportunity.id,
        notes: notes || undefined,
        stake_method: method || undefined,
      })
      toast.push('success', 'Paper bet recorded', `${opportunity.home_team} vs ${opportunity.away_team} — ${opportunity.market} ${opportunity.selection} @ ${oddsNum.toFixed(2)}`)
      onCreated?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record bet')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record paper bet"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={submit} disabled={submitting || !oddsValid}>
            {submitting && <Spinner />}
            Record bet
          </button>
        </>
      }
    >
      <div className="space-y-3 text-sm">
        <div className="rounded bg-slate-50 p-2 text-xs dark:bg-slate-800">
          <div className="font-semibold">
            {opportunity.home_team} vs {opportunity.away_team}
          </div>
          <div className="muted">
            {opportunity.competition} · {opportunity.market} — {opportunity.selection}
          </div>
          <div className="mt-1 grid grid-cols-3 gap-1">
            <span>Model: {pct(opportunity.model_probability)}</span>
            <span>Fair: {fmtOdds(opportunity.fair_odds)}</span>
            <span>EV: {signedPct(opportunity.expected_value)}</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="bet-odds">
              Odds (decimal)
            </label>
            <input id="bet-odds" className="input" type="number" step="0.01" min="1.01" value={odds} onChange={(e) => setOdds(e.target.value)} />
            {opportunity.best_bookmaker && <div className="mt-0.5 text-xs muted">Best: {opportunity.best_bookmaker}</div>}
          </div>
          <div>
            <label className="label" htmlFor="bet-method">
              Stake method
            </label>
            <select id="bet-method" className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="bet-stake">
              Stake
            </label>
            <input id="bet-stake" className="input" type="number" step="0.01" min="0" value={stake} onChange={(e) => setStake(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="bet-notes">
              Notes
            </label>
            <input id="bet-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <div className="rounded border border-slate-200 p-2 text-xs dark:border-slate-700">
          <div className="mb-1 font-semibold uppercase muted">Stake preview</div>
          {previewError && <div className="text-red-700 dark:text-red-300">{previewError}</div>}
          {!previewError && !preview && <div className="muted">{oddsValid ? 'Loading preview...' : 'Enter valid odds to preview stakes.'}</div>}
          {preview && (
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 sm:grid-cols-3">
              {METHODS.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  className={`rounded px-1 py-0.5 text-left hover:bg-slate-100 dark:hover:bg-slate-800 ${method === m.key ? 'font-semibold text-teal-800 dark:text-teal-200' : ''}`}
                  onClick={() => setMethod(m.key)}
                >
                  {m.label}: {money(preview.stakes[m.key])}
                </button>
              ))}
              <span className="muted">Kelly fraction: {pct(preview.kelly_fraction, 2)}</span>
              <span className="muted">Bankroll: {money(preview.bankroll)}</span>
              <span className="muted">Max stake: {pct(preview.max_stake_fraction, 0)} of bankroll</span>
            </div>
          )}
        </div>
        {error && (
          <div role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}
        <p className="text-xs muted">Paper bets are recorded for tracking only. No real bets are placed.</p>
      </div>
    </Modal>
  )
}
