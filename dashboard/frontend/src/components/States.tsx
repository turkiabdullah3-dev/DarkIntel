export function LoadingState() { return <div className="state" role="status"><span className="skeleton"/>Loading investigation data</div> }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="state"><strong>{title}</strong><span>{detail}</span></div> }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="state error" role="alert"><strong>Unable to load data</strong><span>{message}</span>{retry && <button onClick={retry}>Try again</button>}</div> }
