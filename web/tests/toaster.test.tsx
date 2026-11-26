import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { toast } from "../src/components/Toaster";

// El Toaster ya está montado por tests/setup.ts, como en la aplicación.
describe("avisos (toasts)", () => {
  it("anuncia el éxito como estado y el error como alerta, y se cierran con el botón", async () => {
    act(() => { toast.success("Se guardó."); toast.error("No se pudo guardar."); });
    expect(screen.getByRole("status")).toHaveTextContent("Se guardó.");
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar.");
    await userEvent.click(screen.getAllByRole("button", { name: "Cerrar aviso" })[0]);
    expect(screen.queryByText("Se guardó.")).not.toBeInTheDocument();
  });

  it("se cierra solo y no repite el mismo texto", () => {
    vi.useFakeTimers();
    try {
      act(() => { toast.success("Listo."); toast.success("Listo."); });
      expect(screen.getAllByText("Listo.")).toHaveLength(1);
      act(() => { vi.advanceTimersByTime(5100); });
      expect(screen.queryByText("Listo.")).not.toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });
});
