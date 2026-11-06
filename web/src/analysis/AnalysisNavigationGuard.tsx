import { useEffect, useState } from "react";
import { useBlocker } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";

/** Confirma antes de salir de la página, dentro de la aplicación o al cerrarla o recargarla. */
export function AnalysisNavigationGuard({
  onLeave,
  title = "Salir del análisis",
  message = "Si sales, se cancelará la sesión activa y se apagará la cámara. ¿Quieres continuar?",
  confirmLabel = "Cancelar sesión y salir",
}: { onLeave(): Promise<boolean>; title?: string; message?: string; confirmLabel?: string }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search,
  );
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  async function confirmLeave() {
    setLeaving(true);
    try {
      if (await onLeave() && blocker.state === "blocked") blocker.proceed();
    } finally { setLeaving(false); }
  }

  return <ConfirmDialog open={blocker.state === "blocked"} title={title} message={message} confirming={leaving} confirmLabel={confirmLabel} onCancel={() => { if (blocker.state === "blocked") blocker.reset(); }} onConfirm={() => { void confirmLeave(); }} />;
}
