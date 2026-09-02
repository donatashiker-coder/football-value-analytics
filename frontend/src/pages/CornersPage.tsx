import { api } from '@/services/api'
import { OpportunityListPage } from '@/components/OpportunityListPage'

export default function CornersPage() {
  return <OpportunityListPage title="Corners" fetcher={(params, signal) => api.corners(params, signal)} scannerKind="high_corners" />
}
