import { Archive, ClockCounterClockwise, Graph, House, ListMagnifyingGlass, NotePencil, ShieldCheck } from '@phosphor-icons/react'
import { NavLink, Outlet, useParams } from 'react-router-dom'
import { branding } from '../config/branding'

const sections = [
  ['Overview', House, ''], ['Evidence', Archive, 'evidence'], ['Indicators', ListMagnifyingGlass, 'indicators'],
  ['Enrichment', ShieldCheck, 'enrichment'], ['Timeline', ClockCounterClockwise, 'timeline'],
  ['Graph', Graph, 'graph'], ['Findings', NotePencil, 'findings']
] as const

export function Shell() {
  const { caseId } = useParams()
  return <div className="shell">
    <aside className="sidebar">
      <NavLink to="/cases" className="brand" aria-label={`${branding.productName} case registry`}><img src={branding.iconPath} alt=""/><span>{branding.productName}<small>{branding.productTagline}</small></span></NavLink>
      {caseId && <nav aria-label="Case sections">{sections.map(([label, Icon, path]) => <NavLink key={label} end={!path} to={`/cases/${caseId}${path ? `/${path}` : ''}`}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>}
      <div className="localNotice"><ShieldCheck size={17}/><span>Loopback only<small>{branding.ownerName} · No authentication</small></span></div>
    </aside>
    <div className="workspace"><header className="topbar"><div className="topbarBrand"><img src={branding.iconPath} alt=""/><span><b>{branding.productName}</b><small>{branding.productTagline}</small></span></div><div className="caseContext"><span className="muted">Active case</span><strong>{caseId ?? 'Case registry'}</strong></div><NavLink to="/cases" className="quietButton">Switch case</NavLink></header><main><Outlet/></main></div>
  </div>
}
