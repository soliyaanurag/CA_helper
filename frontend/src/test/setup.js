// Runs before every Vitest test file.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup(); // unmount rendered components
  localStorage.clear(); // no session leaks into the next test
  vi.unstubAllGlobals(); // undo fakeApi()'s fetch stub
});
