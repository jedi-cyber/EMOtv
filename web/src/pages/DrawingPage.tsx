import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import { Button } from "../components/Button";
import { DrawingActivity } from "../drawing/DrawingActivity";
import { paths } from "../routes/paths";

/**
 * Actividad de dibujo a pantalla completa, con el aspecto de la pantalla de la
 * persona. No crea una sesión ni usa la cámara, y no registra nada: el dibujo y
 * la emoción elegida quedan solo en esta pantalla mientras está abierta.
 */
export function DrawingPage() {
  const navigate = useNavigate();
  const [hasDrawing, setHasDrawing] = useState(false);
  return <main className="participant-view drawing-view">
    {hasDrawing && <AnalysisNavigationGuard onLeave={async () => true} title="Salir del dibujo"
      message="Si sales, el dibujo se borra: no se guarda en ningún lugar. ¿Quieres salir?" confirmLabel="Salir y borrar" />}
    <div className="participant-view-stage drawing-stage">
      <DrawingActivity onDrawingChange={setHasDrawing} />
    </div>
    <div className="participant-actions">
      <Button variant="ghost" onClick={() => { navigate(paths.analysis); }}>Salir</Button>
    </div>
  </main>;
}
