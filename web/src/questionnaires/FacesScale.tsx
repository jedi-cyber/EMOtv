/**
 * Escala de cinco caritas dibujadas para EMOtv (no copia ninguna escala
 * publicada). Todas usan el mismo trazo y color: ninguna figura es "mejor" que
 * otra. La posición elegida se guarda tal como se dio, sin convertirla en puntaje.
 */
export const FACE_COUNT = 5;

// Curvatura de la boca de cada figura: de hacia abajo a hacia arriba.
const MOUTHS = [-7, -3.5, 0, 3.5, 7];

export function Face({ position, size = 56 }: { position: number; size?: number }) {
  const curve = MOUTHS[position - 1] ?? 0;
  return <svg className="face-figure" width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
    <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" strokeWidth="2.5" />
    <circle cx="17" cy="19" r="2.4" fill="currentColor" />
    <circle cx="31" cy="19" r="2.4" fill="currentColor" />
    <path d={`M15 ${31 - curve / 2} Q24 ${31 + curve} 33 ${31 - curve / 2}`} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
  </svg>;
}

interface FacesScaleProps {
  name: string;
  label: string;
  value: number | null;
  onChange?: (value: number) => void;
  minLabel?: string | null;
  maxLabel?: string | null;
  large?: boolean;
}

export function FacesScale({ name, label, value, onChange, minLabel, maxLabel, large = false }: FacesScaleProps) {
  return <div className="faces-scale">
    <div role="radiogroup" aria-label={label} className="faces-options">
      {Array.from({ length: FACE_COUNT }, (_, index) => index + 1).map((position) =>
        <label key={position} className={`face-option${value === position ? " face-option-selected" : ""}`}>
          <input type="radio" name={name} value={position} checked={value === position} disabled={!onChange}
            aria-label={`Figura ${position} de ${FACE_COUNT}`} onChange={() => onChange?.(position)} />
          <Face position={position} size={large ? 72 : 56} />
        </label>)}
    </div>
    {(minLabel || maxLabel) && <div className="scale-ends"><span>{minLabel}</span><span>{maxLabel}</span></div>}
  </div>;
}
