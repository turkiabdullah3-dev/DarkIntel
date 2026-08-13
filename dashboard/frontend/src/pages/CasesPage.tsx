import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorState, EmptyState, LoadingState } from '../components/States'
import { Page, Status } from '../components/Page'
import { useApi } from '../hooks/useApi'
import type { CaseSummary } from '../types'
import { branding } from '../config/branding'

export function CasesPage() {
  const state = useApi(() => api<{items: CaseSummary[]}>('/cases'), [])
  return <Page title="Case registry" description="Open a local investigation workspace and review its derived analytical views.">
    {state.loading ? <LoadingState/> : state.error ? <ErrorState message={state.error} retry={state.refresh}/> : !state.data?.items.length ? <div className="brandedEmpty"><img src={branding.logoPath} alt={`${branding.productName} logo`}/><EmptyState title="No cases available" detail="Create a case with the DarkIntel CLI to begin."/></div> : <div className="caseGrid">{state.data.items.map(item => <Link className="caseRow" to={`/cases/${item.case_id}`} key={item.case_id}><div><CodeLabel>{item.case_id}</CodeLabel><h2>{item.name}</h2><span>{item.description || 'No description provided'}</span></div><Status tone={item.status === 'open' ? 'good' : 'neutral'}>{item.status}</Status><dl><div><dt>Indicators</dt><dd>{item.indicator_count}</dd></div><div><dt>Evidence</dt><dd>{item.evidence_count}</dd></div><div><dt>Events</dt><dd>{item.timeline_event_count}</dd></div></dl></Link>)}</div>}
  </Page>
}
function CodeLabel({ children }: { children: string }) { return <span className="caseId">{children}</span> }
