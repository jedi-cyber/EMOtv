export interface BarChartRow {
  key: string;
  label: string;
  value: number;
  /** Texto del valor al final de la barra (por ejemplo, «75 %»). */
  valueText: string;
  /** Detalle que aparece al pasar el puntero o al enfocar la fila. */
  detail?: string;
}

interface BarChartProps {
  /** Nombre accesible del gráfico; el título visible lo pone la página. */
  label: string;
  rows: BarChartRow[];
  /** Valor que llena la barra entera; si falta, el mayor de las filas. */
  max?: number;
}

/**
 * Gráfico de barras horizontales de una sola serie. Todas las barras tienen el mismo color:
 * las expresiones no se colorean ni se valoran. La identidad la da la etiqueta, nunca el color.
 */
export function BarChart({ label, rows, max }: BarChartProps) {
  const top = max ?? Math.max(0, ...rows.map((row) => row.value));
  return <ul className="bar-chart" aria-label={label}>
    {rows.map((row) => {
      const width = top > 0 ? Math.min(100, (row.value / top) * 100) : 0;
      const description = row.detail ? `${row.label}: ${row.valueText}, ${row.detail}` : `${row.label}: ${row.valueText}`;
      return <li key={row.key} className="bar-chart-row" tabIndex={0} aria-label={description}>
        <span className="bar-chart-label" aria-hidden="true">{row.label}</span>
        <span className="bar-chart-track" aria-hidden="true">
          {width > 0 && <span className="bar-chart-fill" style={{ width: `${width}%` }} />}
        </span>
        <span className="bar-chart-value" aria-hidden="true">{row.valueText}</span>
        {row.detail && <span className="bar-chart-tip" role="tooltip" aria-hidden="true">{row.detail}</span>}
      </li>;
    })}
  </ul>;
}
