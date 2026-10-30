import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { ImageReviewPage } from "../src/pages/ImageReviewPage";
import { ImagesPage } from "../src/pages/ImagesPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

const state = vi.hoisted(() => ({ data: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : state.data[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
// Sin imágenes reales: la vista previa no se descarga.
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(() => new Promise(() => undefined)),
}));

function withUser(role: UserRole, element: React.ReactNode) {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

const image = (id: string, changes: Record<string, unknown> = {}) => ({
  id, title: `Imagen ${id}`, origin: "Dibujo propio", audience: "children", status: "pending", possible_person: false,
  batch_id: "b1", created_at: "2026-10-20T10:00:00Z", expires_at: "2026-11-19T10:00:00Z", uploaded_by: "usuario1@example.com", ...changes,
});

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => "blob:vista");
  URL.revokeObjectURL = vi.fn();
});

beforeEach(() => {
  state.data = {};
  vi.mocked(apiRequest).mockReset();
});

describe("imágenes del usuario", () => {
  it("cada imagen pide de dónde es, para quién es y la casilla antes de subirla", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ batch_id: "b1", results: [
      { title: "paisaje", accepted: false, image: null,
        message: "Esta imagen parece mostrar a una persona. Para evitar subir fotos de personas, las imágenes con personas las agrega tu docente al banco institucional." },
    ] } as never);
    withUser("student", <ImagesPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Subir imágenes" })[0]);
    const dialog = screen.getByRole("dialog", { name: "Subir imágenes" });
    await userEvent.upload(within(dialog).getByLabelText(/Imágenes \(PNG, JPEG o WebP/),
      new File(["x"], "paisaje.png", { type: "image/png" }));
    const submit = within(dialog).getByRole("button", { name: "Subir imagen" });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("¿De dónde es esta imagen?"), "Dibujo propio");
    await userEvent.click(within(dialog).getByRole("radio", { name: /Para niños/ }));
    expect(submit).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "No es una foto de una persona que pueda identificarse, y tengo derecho a usarla" }));
    await userEvent.click(submit);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/own-stimuli");
    const body = (options as RequestInit).body as FormData;
    expect([body.get("titles"), body.get("origins"), body.get("audiences"), body.get("rights_confirmed")])
      .toEqual(["paisaje", "Dibujo propio", "children", "true"]);
    expect(await screen.findByText(/parece mostrar a una persona/)).toBeInTheDocument();
  });

  it("una imagen pendiente se muestra «En revisión» con su fecha de vencimiento", () => {
    state.data["/own-stimuli"] = [image("1"), image("2", { status: "approved", audience: "adults", expires_at: null })];
    withUser("student", <ImagesPage />);
    expect(screen.getByText("En revisión")).toBeInTheDocument();
    expect(screen.getByText(/se eliminará/)).toBeInTheDocument();
    expect(screen.getByText("Aprobada")).toBeInTheDocument();
  });
});

describe("imágenes por revisar", () => {
  const review = {
    pending: [{ batch_id: "b1", uploaded_by: "usuario1@example.com", uploaded_at: "2026-10-20T10:00:00Z",
      images: [image("1", { possible_person: true }), image("2", { audience: "adults" })] }],
    approved: [],
  };

  it("agrupa por lote, preselecciona lo que eligió el usuario y recuerda eliminar si hay una persona", () => {
    state.data["/own-stimuli/review"] = review;
    withUser("psychologist", <ImageReviewPage />);
    expect(screen.getByRole("heading", { name: /usuario1@example\.com/ })).toBeInTheDocument();
    expect(screen.getByText("Revisar: posible persona")).toBeInTheDocument();
    expect(screen.getAllByText("Si ves a una persona, elimina la imagen.").length).toBeGreaterThanOrEqual(2);
    const [first, second] = screen.getAllByRole("group", { name: "Decisión" });
    expect(within(first).getByRole("radio", { name: "Para niños" })).toBeChecked();
    expect(within(second).getByRole("radio", { name: "Para adultos" })).toBeChecked();
  });

  it("aplica decisiones a varias imágenes y pide un motivo opcional al eliminar", async () => {
    state.data["/own-stimuli/review"] = review;
    vi.mocked(apiRequest).mockResolvedValue([] as never);
    withUser("psychologist", <ImageReviewPage />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Seleccionar las 2 del lote" }));
    const [first] = screen.getAllByRole("group", { name: "Decisión" });
    await userEvent.click(within(first).getByRole("radio", { name: "Eliminar" }));
    await userEvent.click(screen.getByRole("button", { name: "Aplicar a 2 imágenes" }));
    const dialog = screen.getByRole("dialog", { name: "Eliminar imágenes" });
    await userEvent.type(within(dialog).getByLabelText(/Motivo/), "Se ve una persona");
    await userEvent.click(within(dialog).getByRole("button", { name: "Eliminar y aplicar" }));
    const bodies = vi.mocked(apiRequest).mock.calls.map(([, options]) => JSON.parse((options as RequestInit).body as string));
    expect(bodies).toEqual(expect.arrayContaining([
      { image_ids: ["1"], decision: "delete", reason: "Se ve una persona" },
      { image_ids: ["2"], decision: "adults", reason: null },
    ]));
  });
});

describe("imágenes propias en los protocolos", () => {
  it("un protocolo para niños solo ofrece imágenes «Para niños»", async () => {
    state.data["/stimuli"] = [
      { id: "a", title: "Para todos", kind: "emotional", intensity: "mild", audience: "children", scope: "user", approved: true, active: true, category: "Imagen propia", min_age: 1 },
      { id: "b", title: "Solo adultos", kind: "emotional", intensity: "moderate", audience: "adults", scope: "user", approved: true, active: true, category: "Imagen propia", min_age: 1 },
    ];
    withUser("student", <ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    const options = within(screen.getByLabelText("Imagen")).getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Elige una imagen", "Para todos — Imagen propia · Para niños"]);
  });

  it("un protocolo que perdió una imagen dice «Necesita una imagen» y no se usa", () => {
    state.data["/protocols"] = [{ id: "p1", family_id: "p1", version: 1, name: "Secuencia", description: "", for_children: false,
      pre_questionnaire_id: null, post_questionnaire_id: null, steps: [], created_at: "2026-10-20T10:00:00Z",
      owned_by_me: true, used: false, needs_image: true }];
    withUser("student", <ProtocolsPage />);
    expect(screen.getByText("Necesita una imagen")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Usar en el Analizador" })).not.toBeInTheDocument();
  });

  it("muestra los avisos de la cuenta", () => {
    state.data["/notices"] = [{ id: "n1", message: "El protocolo «Secuencia» necesita una imagen.", created_at: "2026-10-20T10:00:00Z" }];
    withUser("student", <ProtocolsPage />);
    expect(screen.getByText("El protocolo «Secuencia» necesita una imagen.")).toBeInTheDocument();
  });
});
