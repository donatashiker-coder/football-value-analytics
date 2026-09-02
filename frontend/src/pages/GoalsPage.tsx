import { api } from '@/services/api'
import { OpportunityListPage } from '@/components/OpportunityListPage'

export default function GoalsPage() {
  return <OpportunityListPage title="Goals" fetcher={(params, signal) => api.goals(params, signal)} scannerKind="high_scoring" />
}
