import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Alert } from "../src/components/Alert";
import { ConfirmDialog } from "../src/components/ConfirmDialog";
import { Spinner } from "../src/components/Spinner";
import { PageState } from "../src/components/PageState";
import { PageHeader } from "../src/components/PageHeader";
import { MemoryRouter } from "react-router-dom";

describe("componentes accesibles", () => {
  it("usa un encabezado de página común con título y acción opcional", () => {
    render(<PageHeader section="Seguimiento" title="Sesiones" description="Consulta tus sesiones." actions={<button>Nueva sesión</button>} />);
    expect(screen.getByRole("heading", { level: 1, name: "Sesiones" })).toBeInTheDocument();
    expect(screen.getByText("Seguimiento")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nueva sesión" })).toBeInTheDocument();
  });
  it("anuncia errores e indicadores de carga", () => {
    render(<><Alert variant="error">Sin conexión</Alert><Spinner label="Cargando sesiones" /></>);
    expect(screen.getByRole("alert")).toHaveTextContent("Sin conexión");
    expect(screen.getByRole("status")).toHaveTextContent("Cargando sesiones");
  });

  it("señala la carga y enlaza ayuda solo para errores de conexión", () => {
    const retry = vi.fn();
    const view = render(<MemoryRouter><PageState loading error="" onRetry={retry} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando información");
    expect(view.container.querySelector(".loading-placeholder")).toHaveAttribute("aria-hidden", "true");
    view.rerender(<MemoryRouter><PageState loading={false} error="Servicio no disponible" connectionError onRetry={retry} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Ayuda de conexión" })).toHaveAttribute("href", "/connection-error");
    view.rerender(<MemoryRouter><PageState loading={false} error="Datos inválidos" onRetry={retry} /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "Ayuda de conexión" })).not.toBeInTheDocument();
  });

  it("confina el foco, permite Escape y restaura el foco al cerrar", async () => {
    const user = userEvent.setup(); const cancel = vi.fn(); const confirm = vi.fn();
    const props = { title: "Eliminar actividad", message: "Confirma la eliminación", onCancel: cancel, onConfirm: confirm };
    const view = render(<><button>Abrir</button><ConfirmDialog {...props} open={false} /></>);
    const trigger = screen.getByRole("button", { name: "Abrir" }); trigger.focus();
    view.rerender(<><button>Abrir</button><ConfirmDialog {...props} open /></>);
    expect(screen.getByRole("alertdialog")).toHaveAccessibleName("Eliminar actividad");
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Confirmar" })).toHaveFocus();
    await user.tab(); expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
    await user.keyboard("{Escape}"); expect(cancel).toHaveBeenCalledOnce();
    view.rerender(<><button>Abrir</button><ConfirmDialog {...props} open={false} /></>);
    expect(trigger).toHaveFocus(); expect(confirm).not.toHaveBeenCalled();
  });

  it("no permite cancelar ni repetir acciones durante una confirmación", async () => {
    const cancel = vi.fn(); const confirm = vi.fn(); const user = userEvent.setup();
    render(<ConfirmDialog open confirming title="Cancelar" message="Procesando" onCancel={cancel} onConfirm={confirm} />);
    await user.keyboard("{Escape}");
    fireEvent.mouseDown(screen.getByRole("alertdialog").parentElement!);
    expect(cancel).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Procesando…" })).toBeDisabled();
  });
});
