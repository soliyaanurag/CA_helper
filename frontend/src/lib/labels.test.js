import { describe, expect, it } from "vitest";

import { COMPLIANCE_STATUS_LABELS, ENGAGEMENT_STATUS_LABELS, label } from "./labels";

describe("label", () => {
  it("returns the display text for a known code", () => {
    expect(label(COMPLIANCE_STATUS_LABELS, "docs_pending")).toBe("Docs pending");
    expect(label(ENGAGEMENT_STATUS_LABELS, "expired")).toBe("Expired");
  });

  it("falls back to the code for an unknown value", () => {
    expect(label(COMPLIANCE_STATUS_LABELS, "brand_new_status")).toBe("brand_new_status");
  });

  it("uses lowercase snake_case codes only", () => {
    const codes = [
      ...Object.keys(COMPLIANCE_STATUS_LABELS),
      ...Object.keys(ENGAGEMENT_STATUS_LABELS),
    ];
    for (const code of codes) expect(code).toMatch(/^[a-z]+(_[a-z]+)*$/);
  });
});
