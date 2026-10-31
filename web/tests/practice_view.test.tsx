import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { ParticipantPractice, ParticipantViewState } from "../src/api/types";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";

vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const practice: ParticipantPractice = {
  instruction: "Muestra alegría", level: 0.4, achieved: false, message: null, frame_interval_ms: 500,
};
const base: ParticipantViewState = {
  phase: "stimuli", message: null, stimulus: null, remaining_seconds: 12, capture_frames: false,
  frame_interval_ms: 500, abstract_notice: null, practice,
};
// Lo que la pantalla de la persona nunca recibe ni muestra.
const FORBIDDEN_KEYS = ["emotion", "expression", "confidence", "probability", "distribution", "quality",
  "quality_issues", "calibrated_emotion", "target_expression", "peak_level", "captures", "markers", "note"];

function participant(view: ParticipantViewState) {
  vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? view : { stopped: true }) as never);
  return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
    <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
  </MemoryRouter>);
}

function keys(value: unknown): string[] {
  if (value == null || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([key, item]) => [key, ...keys(item)]);
}

beforeEach(() => { vi.mocked(apiRequest).mockReset(); vi.mocked(apiBlob).mockReset(); });

describe("ejercicio de práctica en la pantalla de la persona", () => {
  it("muestra la instrucción grande y una figura que crece con el nivel, sin números", async () => {
    participant(base);
    expect(await screen.findByText("Muestra alegría")).toHaveClass("participant-instruction");
    const signal = screen.getByRole("meter", { name: "Señal del ejercicio" });
    expect(signal).toHaveAttribute("aria-valuenow", "0.4");
    expect(signal.style.getPropertyValue("--practice-level")).toBe("0.4");
    expect(document.body.textContent).not.toMatch(/0[.,]4|40|%|alegría \(|confianza|calidad|probab/i);
    expect(screen.getByRole("button", { name: "Quiero parar" })).toBeVisible();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("al lograrlo muestra una confirmación breve", async () => {
    participant({ ...base, practice: { ...practice, level: 1, achieved: true, message: "¡Lo lograste!" } });
    expect(await screen.findByRole("status")).toHaveTextContent("¡Lo lograste!");
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "1");
  });

  it("sin lograrlo no hay mensaje de fracaso", async () => {
    participant({ ...base, practice: { ...practice, level: 0.2 } });
    expect(await screen.findByText("Muestra alegría")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("");
    expect(document.body.textContent).not.toMatch(/no lo lograste|fallaste|intenta|mal|incorrect/i);
  });

  it("con la señal apagada muestra solo la instrucción", async () => {
    participant({ ...base, practice: { ...practice, level: null } });
    expect(await screen.findByText("Muestra alegría")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  });

  it("muestra la ilustración cuando el ejercicio la tiene", async () => {
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    URL.createObjectURL = vi.fn(() => "blob:ilustracion");
    URL.revokeObjectURL = vi.fn();
    participant({ ...base, stimulus: { exposure: "0-1" } });
    expect(await screen.findByRole("img", { name: "Imagen de apoyo" })).toHaveAttribute("src", "blob:ilustracion");
    expect(screen.getByText("Muestra alegría")).toBeInTheDocument();
  });

  it("los pasos de imagen siguen como antes", async () => {
    const { practice: _, ...stimulusView } = base;
    participant({ ...stimulusView, message: "Mira la imagen." });
    expect(await screen.findByText("Mira la imagen.")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.queryByText("Muestra alegría")).not.toBeInTheDocument();
  });
});

describe("contrato de la respuesta de la práctica", () => {
  it("solo trae instrucción, nivel, logro, mensaje e intervalo", () => {
    expect(Object.keys(practice).sort()).toEqual(["achieved", "frame_interval_ms", "instruction", "level", "message"]);
  });

  it("no tiene claves prohibidas en ningún estado", () => {
    for (const view of [base, { ...base, practice: { ...practice, level: null } },
      { ...base, practice: { ...practice, achieved: true, level: 1, message: "¡Lo lograste!" } }]) {
      expect(keys(view).filter((key) => FORBIDDEN_KEYS.includes(key))).toEqual([]);
    }
  });
});
