import type { ReactNode } from 'react'

export type Column<T> = { key: string; label: string; render: (item: T) => ReactNode }
export function DataTable<T>({ columns, items, onSelect }: { columns: Column<T>[]; items: T[]; onSelect?: (item: T) => void }) {
  return <div className="tableWrap"><table><thead><tr>{columns.map(column => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>
    {items.map((item, index) => <tr key={index} tabIndex={onSelect ? 0 : undefined} onClick={() => onSelect?.(item)} onKeyDown={event => event.key === 'Enter' && onSelect?.(item)}>{columns.map(column => <td key={column.key}>{column.render(item)}</td>)}</tr>)}
  </tbody></table></div>
}

export function Pager({ total, offset, limit, change }: { total: number; offset: number; limit: number; change: (value: number) => void }) {
  return <div className="pager"><span>{total ? `${offset + 1}-${Math.min(offset + limit, total)} of ${total}` : '0 results'}</span><button disabled={!offset} onClick={() => change(Math.max(0, offset - limit))}>Previous</button><button disabled={offset + limit >= total} onClick={() => change(offset + limit)}>Next</button></div>
}
