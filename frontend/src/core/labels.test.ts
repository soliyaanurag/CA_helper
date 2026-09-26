import { describe, expect, it } from "vitest";

import { label, USER_ROLE_LABELS } from "./labels";

describe("label", () => {
  it("returns the display text for a known code", () => {
    expect(label(USER_ROLE_LABELS, "ca")).toBe("Chartered Accountant");
  });

  it("falls back to the code for an unknown value", () => {
    expect(label(USER_ROLE_LABELS, "brand_new_role")).toBe("brand_new_role");
  });
});
