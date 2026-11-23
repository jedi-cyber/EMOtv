import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { Toaster, toast } from "../src/components/Toaster";

// Los avisos (toasts) se muestran en una zona propia, montada una vez como en la aplicación.
beforeEach(() => { render(createElement(Toaster)); });
afterEach(() => { act(() => toast.clear()); cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
