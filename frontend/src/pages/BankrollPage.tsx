import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { localDateTime, money, num, pct, signedPct } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard, toneForSigned } from '@/components/StatCard'
import { EmptyState, ErrorState, InfoBox, LoadingState } from '@/components/States'
import { DrawdownChart, EquityChart } from '@/components/charts'

export default function BankrollPage() {
  const { data, loading, error, refetch } = useApi((signal) => api.bankroll(signal), [])

  if (loading) return <LoadingState label="Loading bankroll" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="Bankroll DATA UNAVAILABLE." />

  const drawdownSeries = computeDrawdown(data.equity_curve)

  return (
    <div>
      <PageHeader title="Bankroll" subtitle="Paper bankroll only. No real bets are placed by this system." />
      <div className="space-y-4">
        <InfoBox>{data.note ?? 'This bankroll tracks paper bets for evaluation. Statistical analysis is not a guarantee of future results.'}</InfoBox>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <StatCard label="Starting bankroll" value={money(data.starting_bankroll)} />
          <StatCard label="Current bankroll" value={money(data.current_bankroll)} tone={toneForSigned(data.profit)} />
          <StatCard label="Profit" value={money(data.profit)} tone={toneForSigned(data.profit)} />
          <StatCard label="ROI" value={signedPct(data.roi)} tone={toneForSigned(data.roi)} hint={`Staked ${money(data.total_staked)}`} />
          <StatCard label="Max drawdown" value={money(data.max_drawdown)} tone="red" />
          <StatCard label="Avg CLV" value={signedPct(data.average_clv)} tone={toneForSigned(data.average_clv)} />
          <StatCard label="Open bets" value={data.open_bets} hint={`Open stake ${money(data.open_stake)}`} />
          <StatCard label="Settled" value={data.settled_bets} hint={`${data.wins}W / ${data.losses}L / ${data.pushes}P`} />
          <StatCard label="Strike rate" value={pct(data.strike_rate)} />
          <StatCard label="Avg odds" value={num(data.average_odds)} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="Equity curve">
            <EquityChart data={data.equity_curve} />
          </Section>
          <Section title="Drawdown">
            <EquityDrawdown data={drawdownSeries} />
          </Section>
        </div>
        <Section title="Snapshots">
          {data.snapshots.length === 0 ? (
            <EmptyState title="No bankroll snapshots yet." />
          ) : (
            <div className="table-wrap">
              <table className="table text-xs">
                <thead>
                  <tr>
                    <th>As of</th>
                    <th className="text-right">Bankroll</th>
                    <th className="text-right">Profit</th>
                    <th className="text-right">ROI</th>
                    <th className="text-right">Max drawdown</th>
                  </tr>
                </thead>
                <tbody>
                  {data.snapshots.map((s, i) => (
                    <tr key={i}>
                      <td>{localDateTime(s.as_of)}</td>
                      <td className="text-right num">{money(s.bankroll)}</td>
                      <td className="text-right num">{money(s.profit)}</td>
                      <td className="text-right num">{signedPct(s.roi)}</td>
                      <td className="text-right num">{money(s.max_drawdown)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

function computeDrawdown(curve: { t: string; equity: number }[]) {
  let peak = -Infinity
  return curve.map((p) => {
    peak = Math.max(peak, p.equity)
    return { t: p.t, equity: p.equity, drawdown: peak - p.equity }
  })
}

function EquityDrawdown({ data }: { data: { t: string; equity: number; drawdown: number }[] }) {
  return <DrawdownChart data={data} height={240} />
}
