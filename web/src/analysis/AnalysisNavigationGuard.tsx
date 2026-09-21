import { useEffect, useState } from "react";
import { useBlocker } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";

export function AnalysisNavigationGuard({ onLeave }: { onLeave(): Promise<boolean> }) {
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

  return <ConfirmDialog open={blocker.state === "blocked"} title="Salir del análisis" message="Si sales, se cancelará la sesión activa y se apagará la cámara. ¿Quieres continuar?" confirming={leaving} confirmLabel="Cancelar sesión y salir" onCancel={() => { if (blocker.state === "blocked") blocker.reset(); }} onConfirm={() => { void confirmLeave(); }} />;
}
