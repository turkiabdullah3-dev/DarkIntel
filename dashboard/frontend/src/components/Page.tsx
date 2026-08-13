import type { ReactNode } from 'react'
export function Page({ title, description, action, children }: { title: string; description: string; action?: ReactNode; children: ReactNode }) {
  return <section className="page"><div className="pageHead"><div><h1>{title}</h1><p>{description}</p></div>{action}</div>{children}</section>
}
export const Code = ({ children }: { children: ReactNode }) => <code className="code">{children}</code>
export const Status = ({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral'|'good'|'warn'|'bad' }) => <span className={`status ${tone}`}>{children}</span>
