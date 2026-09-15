interface SpinnerProps { label?: string }

export function Spinner({ label = "Cargando" }: SpinnerProps) {
  return <span className="spinner-wrap" role="status"><span className="spinner" aria-hidden="true" />{label}<span className="sr-only">…</span></span>;
}
