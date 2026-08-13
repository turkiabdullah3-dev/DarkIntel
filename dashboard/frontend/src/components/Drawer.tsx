import type { ReactNode } from 'react'
export function Drawer({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  return <div className="drawerBackdrop" onMouseDown={close}><aside className="drawer" role="dialog" aria-modal="true" aria-label={title} onMouseDown={event => event.stopPropagation()}><header><h2>{title}</h2><button onClick={close} aria-label="Close detail panel">Close</button></header>{children}</aside></div>
}
