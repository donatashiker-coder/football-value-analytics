import { api } from '@/services/api'
import { OpportunityListPage } from '@/components/OpportunityListPage'

export default function LowScoringPage() {
  return <OpportunityListPage title="Low Scoring" fetcher={(params, signal) => api.lowScoring(params, signal)} scannerKind="low_scoring" />
}
