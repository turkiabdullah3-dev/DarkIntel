import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Page, Status } from '../components/Page'
import { ErrorState, LoadingState } from '../components/States'
import { useApi } from '../hooks/useApi'
import type { CaseDetail } from '../types'

export function OverviewPage() {
  const { caseId = '' } = useParams(); const state = useApi(() => api<CaseDetail>(`/cases/${caseId}`), [caseId])
  if (state.loading) return <LoadingState/>; if (state.error || !state.data) return <ErrorState message={state.error ?? 'Case unavailable'} retry={state.refresh}/>
  const item = state.data, metrics = item.overview
  const cards = [['Evidence', metrics.evidence], ['Unique IOCs', metrics.indicators], ['Onion targets', metrics.onion_targets], ['Enrichment', metrics.enrichment_records], ['Timeline', metrics.timeline_events], ['Graph nodes', metrics.graph_nodes], ['Graph edges', metrics.graph_edges]]
  const max = Math.max(1, ...Object.values(metrics.ioc_types))
  return <Page title={item.name} description={item.description || 'Local CTI investigation'} action={<Status tone={item.status === 'open' ? 'good' : 'neutral'}>{item.status}</Status>}>
    <div className="caseMeta"><span>{item.case_id}</span><span>Created {format(item.created_at)}</span><span>Updated {format(item.updated_at)}</span>{item.tags.map(tag => <Status key={tag}>{tag}</Status>)}</div>
    <div className="metricGrid">{cards.map(([label, value]) => <article className="metric" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>
    <div className="overviewGrid"><section className="panel"><h2>IOC distribution</h2>{Object.entries(metrics.ioc_types).length ? <div className="distribution">{Object.entries(metrics.ioc_types).map(([type, count]) => <div key={type}><span>{type}</span><i style={{width: `${Math.max(4, count / max * 100)}%`}}/><strong>{count}</strong></div>)}</div> : <p className="muted">No indicators extracted.</p>}</section>
    <section className="panel"><h2>Recent activity</h2>{metrics.recent_events.length ? <div className="activity">{metrics.recent_events.slice(0,6).map(event => <div key={event.event_id}><span>{format(event.timestamp)}</span><strong>{event.title}</strong><small>{event.event_type}</small></div>)}</div> : <p className="muted">No timeline activity.</p>}</section></div>
  </Page>
}
const format = (value: string) => new Date(value).toLocaleString()
