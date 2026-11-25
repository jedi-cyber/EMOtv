import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConductorLiveReading, CONDUCTOR_READING_NOTICE } from "../src/guided/ConductorLiveReading";

// La lectura en vivo es solo para quien conduce: la expresión estimada y su confianza.

describe("lo que estima la cámara, para quien conduce", () => {
  it("muestra la expresión estimada, la confianza y las cinco expresiones", () => {
    render(<ConductorLiveReading reading={{ face_detected: true, emotion: "neutral", confidence: 0.62,
      distribution: [{ emotion: "neutral", probability: 0.62 }, { emotion: "sadness", probability: 0.18 }],
      quality_issues: [], seconds_ago: 0.4 }} />);
    const card = within(screen.getByRole("region", { name: "Lo que estima la cámara" }));
    expect(card.getByText(/Solo lo ves tú/)).toBeInTheDocument();
    expect(card.getByText("62 %")).toBeInTheDocument();
    expect(card.getByRole("list", { name: "Expresiones estimadas" }).children).toHaveLength(2);
    expect(card.getByText(CONDUCTOR_READING_NOTICE)).toBeInTheDocument();
  });

  it("sin rostro, dice por qué y qué pedir; sin cuadros, lo explica", () => {
    const { rerender } = render(<ConductorLiveReading reading={{ face_detected: false, emotion: null, confidence: null,
      distribution: [], quality_issues: ["too_dark"], seconds_ago: 0 }} />);
    expect(screen.getByText(/hay poca luz\. Pide a la persona que mire de frente/)).toBeInTheDocument();
    rerender(<ConductorLiveReading reading={null} />);
    expect(screen.getByText(/Sin lectura en este momento/)).toBeInTheDocument();
  });
});
