import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import { applyBrandingMetadata } from '../config/branding'

applyBrandingMetadata()

const respond = (body: unknown, ok = true) => vi.spyOn(globalThis, 'fetch').mockResolvedValue({
  ok, json: async () => body
} as Response)

afterEach(() => vi.restoreAllMocks())

describe('dashboard shell and case views', () => {
  it('shows a loading state and then the case registry', async () => {
    respond({items: [{case_id: 'CASE-2026-0001', name: 'Operation Lantern', description: 'Local case',
      status: 'open', created_at: '2026-08-13T00:00:00Z', updated_at: '2026-08-13T00:00:00Z', tags: [],
      indicator_count: 4, evidence_count: 2, timeline_event_count: 3, graph_node_count: 5}]})
    render(<MemoryRouter initialEntries={['/cases']}><App/></MemoryRouter>)
    expect(screen.getByRole('status')).toHaveTextContent('Loading investigation data')
    expect(await screen.findByText('Operation Lantern')).toBeVisible()
    expect(screen.getByText('4')).toBeVisible()
    expect(screen.getByLabelText('DarkIntel case registry')).toBeVisible()
    expect(screen.getAllByText('DarkIntel').length).toBeGreaterThan(0)
    expect(screen.getByText(/Turki Almuraykhi/)).toBeVisible()
    expect(document.title).toBe('DarkIntel')
  })

  it('renders hostile artifact strings as text, never markup', async () => {
    respond({items: [{case_id: 'CASE-2026-0001', name: '<img src=x onerror=alert(1)>',
      description: '<script>window.pwned=true</script>', status: 'open', created_at: '', updated_at: '', tags: [],
      indicator_count: 0, evidence_count: 0, timeline_event_count: 0, graph_node_count: 0}]})
    const {container} = render(<MemoryRouter initialEntries={['/cases']}><App/></MemoryRouter>)
    expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeVisible()
    expect(screen.getByText('<script>window.pwned=true</script>')).toBeVisible()
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img[src="x"]')).toBeNull()
  })

  it('shows a safe API error and allows retry', async () => {
    respond({error: {code: 'INTERNAL_ERROR', message: 'The request could not be completed.'}}, false)
    render(<MemoryRouter initialEntries={['/cases']}><App/></MemoryRouter>)
    expect(await screen.findByRole('alert')).toHaveTextContent('The request could not be completed.')
    expect(screen.getByRole('button', {name: 'Try again'})).toBeEnabled()
  })

  it('shows the complete branded logo in the empty case state', async () => {
    respond({items: []})
    render(<MemoryRouter initialEntries={['/cases']}><App/></MemoryRouter>)
    expect(await screen.findByAltText('DarkIntel logo')).toBeVisible()
    expect(screen.getByText('No cases available')).toBeVisible()
  })

  it('loads the case overview route and primary navigation', async () => {
    respond({case_id: 'CASE-2026-0001', name: 'Operation Lantern', description: 'Investigation', status: 'open',
      created_at: '2026-08-13T00:00:00Z', updated_at: '2026-08-13T00:00:00Z', tags: ['cti'],
      indicator_count: 4, evidence_count: 2, timeline_event_count: 3, graph_node_count: 5,
      overview: {evidence: 2, indicators: 4, onion_targets: 1, enrichment_records: 2, timeline_events: 3,
        graph_nodes: 5, graph_edges: 4, ioc_types: {domain: 3, ipv4: 1}, recent_events: []}})
    render(<MemoryRouter initialEntries={['/cases/CASE-2026-0001']}><App/></MemoryRouter>)
    expect(await screen.findByRole('heading', {name: 'Operation Lantern'})).toBeVisible()
    expect(screen.getByRole('navigation', {name: 'Case sections'})).toBeVisible()
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/cases/CASE-2026-0001', expect.anything()))
  })
})
