import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { LoadingState } from '@/components/States'
import { StatusProvider } from '@/hooks/useStatus'
import { ToastProvider } from '@/hooks/useToast'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const TodayMatches = lazy(() => import('@/pages/TodayMatches'))
const MatchPage = lazy(() => import('@/pages/MatchPage'))
const ValueBets = lazy(() => import('@/pages/ValueBets'))
const GoalsPage = lazy(() => import('@/pages/GoalsPage'))
const CornersPage = lazy(() => import('@/pages/CornersPage'))
const LowScoringPage = lazy(() => import('@/pages/LowScoringPage'))
const TeamAnalysis = lazy(() => import('@/pages/TeamAnalysis'))
const TeamPage = lazy(() => import('@/pages/TeamPage'))
const LeagueAnalysis = lazy(() => import('@/pages/LeagueAnalysis'))
const LeaguePage = lazy(() => import('@/pages/LeaguePage'))
const OddsPage = lazy(() => import('@/pages/OddsPage'))
const Backtesting = lazy(() => import('@/pages/Backtesting'))
const BacktestDetailPage = lazy(() => import('@/pages/BacktestDetailPage'))
const PaperBets = lazy(() => import('@/pages/PaperBets'))
const BankrollPage = lazy(() => import('@/pages/BankrollPage'))
const ModelPerformance = lazy(() => import('@/pages/ModelPerformance'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const DataSourcesPage = lazy(() => import('@/pages/DataSourcesPage'))
const NotFound = lazy(() => import('@/pages/NotFound'))

export default function App() {
  return (
    <StatusProvider>
      <ToastProvider>
        <Layout>
          <Suspense fallback={<LoadingState label="Loading page" />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/matches" element={<TodayMatches />} />
              <Route path="/matches/:id" element={<MatchPage />} />
              <Route path="/value" element={<ValueBets />} />
              <Route path="/goals" element={<GoalsPage />} />
              <Route path="/corners" element={<CornersPage />} />
              <Route path="/low-scoring" element={<LowScoringPage />} />
              <Route path="/teams" element={<TeamAnalysis />} />
              <Route path="/teams/:id" element={<TeamPage />} />
              <Route path="/leagues" element={<LeagueAnalysis />} />
              <Route path="/leagues/:code" element={<LeaguePage />} />
              <Route path="/odds" element={<OddsPage />} />
              <Route path="/odds/:fixtureId" element={<OddsPage />} />
              <Route path="/backtests" element={<Backtesting />} />
              <Route path="/backtests/:id" element={<BacktestDetailPage />} />
              <Route path="/paper-bets" element={<PaperBets />} />
              <Route path="/bankroll" element={<BankrollPage />} />
              <Route path="/performance" element={<ModelPerformance />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/data-sources" element={<DataSourcesPage />} />
              <Route path="/dashboard" element={<Navigate to="/" replace />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </Layout>
      </ToastProvider>
    </StatusProvider>
  )
}
