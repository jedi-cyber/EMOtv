import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { SessionState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { Button } from "../src/components/Button";
import { CameraFrame } from "../src/components/CameraFrame";
import { Checkbox } from "../src/components/Checkbox";
import { Modal } from "../src/components/Modal";
import { PageState } from "../src/components/PageState";
import { StatusChip, toneForSession } from "../src/components/StatusChip";
import { AppLayout } from "../src/layouts/AppLayout";
import { activityOutcomeName, emotionModelName, sessionStateName } from "../src/sessions/labels";

describe("componentes base de DESIGN.md", () => {
  it("Button deshabilitado no ejecuta la acción", async () => {
    const onClick = vi.fn();
    render(<Button variant="primary" disabled onClick={onClick}>Registrar esta expresión</Button>);
    const button = screen.getByRole("button", { name: "Registrar esta expresión" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("Button en carga conserva su texto, queda deshabilitado y lo anuncia", () => {
    render(<Button variant="primary" loading>Guardar</Button>);
    const button = screen.getByRole("button", { name: "Guardar" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("type", "button");
  });

  it("Checkbox usa todo el texto como etiqueta", async () => {
    render(<Checkbox defaultChecked={false}>Leer instrucciones en voz alta</Checkbox>);
    const box = screen.getByRole("checkbox", { name: "Leer instrucciones en voz alta" });
    expect(box).not.toBeChecked();
    await userEvent.click(screen.getByText("Leer instrucciones en voz alta"));
    expect(box).toBeChecked();
  });

  it.each([
    ["completed", "success"],
    ["in_progress", "progress"],
    ["recognized", "progress"],
    ["created", "neutral"],
    ["cancelled", "neutral"],
  ] as [SessionState, string][])("StatusChip de sesión %s usa el tono %s con texto", (state, tone) => {
    const view = render(<StatusChip tone={toneForSession(state)}>{sessionStateName(state)}</StatusChip>);
    const chip = view.container.querySelector(".status-chip");
    expect(chip).toHaveClass(`status-chip-${tone}`);
    expect(chip).toHaveTextContent(sessionStateName(state));
    expect(chip?.querySelector(".status-chip-dot")).toHaveAttribute("aria-hidden", "true");
  });

  it("Modal se cierra con Escape y devuelve el foco al botón que lo abrió", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return <>
        <button type="button" onClick={() => setOpen(true)}>Leer la política</button>
        <Modal open={open} title="Política de consentimiento" onClose={() => setOpen(false)}
          footer={<Button variant="primary" onClick={() => setOpen(false)}>Aceptar la política</Button>}>
          <p>Texto de la política.</p>
        </Modal>
      </>;
    }
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Leer la política" });
    await userEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Política de consentimiento" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("heading", { name: "Política de consentimiento" })).toHaveFocus();
    await userEvent.tab();
    await userEvent.tab();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Cerrar" })).toHaveFocus(); // el foco no sale del modal
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("CameraFrame dibuja cuatro marcas decorativas y marca el estado estable", () => {
    const view = render(<CameraFrame stable><video aria-label="Vista previa de tu cámara" /></CameraFrame>);
    const frame = view.container.querySelector(".camera-frame");
    expect(frame?.querySelectorAll(".frame-mark[aria-hidden='true']")).toHaveLength(4);
    expect(frame).toHaveClass("is-stable");
  });
});

describe("menú lateral en móvil", () => {
  function renderLayout() {
    return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/dashboard"]}><Routes>
        <Route element={<AppLayout />}><Route path="dashboard" element={<p>Inicio</p>} /></Route>
      </Routes></MemoryRouter>
    </AuthContext.Provider>);
  }

  it("se abre desde la barra superior y se cierra con su botón, devolviendo el foco", async () => {
    renderLayout();
    await userEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(screen.getByRole("link", { name: "Inicio" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Cerrar navegación" }));
    expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Cerrar navegación" })).not.toBeInTheDocument();
  });

  it("se cierra al tocar fuera y muestra la sección actual y la aclaración de alcance", async () => {
    renderLayout();
    expect(screen.getByRole("banner")).toHaveTextContent("Inicio");
    expect(screen.queryByText("Estás en")).not.toBeInTheDocument();
    expect(screen.getByText("EMOtv estima expresiones; no diagnostica")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    await userEvent.click(screen.getByRole("button", { name: "Cerrar panel de navegación" }));
    expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("estados de página y etiquetas", () => {
  it.each([
    [403, "No tienes permiso para ver esta información"],
    [404, "No encontramos lo que buscas"],
  ])("el error %i ofrece volver al inicio en lugar de reintentar", (status, text) => {
    render(<MemoryRouter><PageState loading={false} error="Detalle técnico" errorStatus={status} onRetry={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent(text);
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    expect(screen.queryByText("Detalle técnico")).not.toBeInTheDocument();
  });

  it("nunca muestra claves técnicas desconocidas", () => {
    expect(sessionStateName("IN_PROGRESS")).toBe("Estado desconocido");
    expect(activityOutcomeName("timeout")).toBe("Sin resultado");
    expect(emotionModelName("ferplus_onnx")).toBe("FER+");
    expect(emotionModelName("otro_modelo")).toBe("Otro modelo");
  });
});
