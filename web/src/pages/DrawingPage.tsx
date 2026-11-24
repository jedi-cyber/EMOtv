import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import type { Stimulus } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { Button } from "../components/Button";
import { StimulusImage } from "../components/StimulusImage";
import { DrawingActivity } from "../drawing/DrawingActivity";
import { paths } from "../routes/paths";

/** Cuántas imágenes se pueden elegir para una ronda de dibujos. */
export const MAX_DRAWING_IMAGES = 10;

/**
 * Actividad de dibujo a pantalla completa, con el aspecto de la pantalla de la
 * persona. Antes de empezar, quien conduce elige imágenes aprobadas (la persona
 * dibuja una cara a partir de cada una, en el orden elegido) o empieza sin
 * imagen. Solo se dibuja: no se pregunta qué emoción se quiso dibujar. No crea
 * una sesión ni usa la cámara, y no registra nada: el dibujo queda solo en esta
 * pantalla mientras está abierta.
 */
export function DrawingPage() {
  const navigate = useNavigate();
  const [hasDrawing, setHasDrawing] = useState(false);
  const query = useApiQuery<Stimulus[]>("/stimuli");
  const offered = (query.data ?? []).filter((item) => item.active && item.approved);
  const [chosen, setChosen] = useState<Stimulus[]>([]);
  // null: todavía se eligen las imágenes; [] sin imagen; si no, las imágenes en orden.
  const [plan, setPlan] = useState<Stimulus[] | null>(null);
  const [index, setIndex] = useState(0);

  function toggle(item: Stimulus) {
    setChosen((current) => current.some((other) => other.id === item.id)
      ? current.filter((other) => other.id !== item.id)
      : current.length < MAX_DRAWING_IMAGES ? [...current, item] : current);
  }

  function begin(images: Stimulus[]) { setPlan(images); setIndex(0); }
  function restart() { setPlan(null); setIndex(0); setHasDrawing(false); }

  const image = plan && plan.length > 0 ? plan[index] : null;
  const last = plan !== null && index >= plan.length - 1;

  return <main className="participant-view drawing-view">
    {hasDrawing && <AnalysisNavigationGuard onLeave={async () => true} title="Salir del dibujo"
      message="Si sales, el dibujo se borra: no se guarda en ningún lugar. ¿Quieres salir?" confirmLabel="Salir y borrar" />}
    {plan === null
      ? <div className="participant-view-stage drawing-stage">
        <section className="drawing-setup" aria-labelledby="drawing-setup-title">
          <h1 id="drawing-setup-title">Dibuja una cara</h1>
          <p className="muted">Elige las imágenes que la persona mirará antes de dibujar, en el orden en que las tocas, o empieza sin imagen.
            EMOtv no compara el dibujo con la imagen.</p>
          <div className="inline-actions">
            <Button variant="primary" disabled={chosen.length === 0} onClick={() => begin(chosen)}>
              {chosen.length === 0 ? "Empezar con imágenes" : chosen.length === 1 ? "Empezar con 1 imagen" : `Empezar con ${chosen.length} imágenes`}
            </Button>
            <Button variant="secondary" onClick={() => begin([])}>Empezar sin imagen</Button>
          </div>
          {query.loading && <p className="muted" role="status">Cargando imágenes…</p>}
          {!query.loading && offered.length === 0 && <p className="muted">No hay imágenes aprobadas para elegir. Puedes dibujar sin imagen.</p>}
          {offered.length > 0 && <ul className="drawing-pick-list" aria-label="Imágenes para elegir">
            {offered.map((item) => {
              const position = chosen.findIndex((other) => other.id === item.id);
              return <li key={item.id}>
                <button type="button" className="drawing-pick" aria-pressed={position >= 0}
                  disabled={position < 0 && chosen.length >= MAX_DRAWING_IMAGES} onClick={() => toggle(item)}>
                  <StimulusImage id={item.id} alt="" />
                  <span>{item.title}</span>
                  {position >= 0 && <span className="drawing-pick-order" aria-label={`Imagen ${position + 1}`}>{position + 1}</span>}
                </button>
              </li>;
            })}
          </ul>}
        </section>
      </div>
      : <div className="participant-view-stage drawing-stage">
        {image && <p className="muted" role="status">Imagen {index + 1} de {plan.length}</p>}
        <DrawingActivity key={image?.id ?? "sin-imagen"} onDrawingChange={setHasDrawing} askEmotion={false}
          model={image ? <StimulusImage id={image.id} alt="Imagen para mirar antes de dibujar" className="drawing-model" /> : undefined}
          next={image ? (last ? { label: "Terminar", onSelect: restart }
            : { label: "Siguiente imagen", onSelect: () => { setIndex(index + 1); setHasDrawing(false); } }) : undefined} />
      </div>}
    <div className="participant-actions">
      {plan !== null && <Button variant="ghost" onClick={restart}>Elegir otras imágenes</Button>}
      <Button variant="ghost" onClick={() => { navigate(paths.games); }}>Salir</Button>
    </div>
  </main>;
}
