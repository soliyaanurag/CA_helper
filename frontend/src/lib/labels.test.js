import { describe, expect, it } from "vitest";

import { filingFormLabel, label, USER_ROLE_LABELS } from "./labels";

describe("label", () => {
  it("returns the display text for a known code", () => {
    expect(label(USER_ROLE_LABELS, "ca")).toBe("Chartered Accountant");
  });

  it("falls back to the code for an unknown value", () => {
    expect(label(USER_ROLE_LABELS, "brand_new_role")).toBe("brand_new_role");
  });
});

describe("filingFormLabel", () => {
  it("shows the TDS returns under their new names from tax year 2026-27", () => {
    expect(filingFormLabel("tds_24q", "Q2 2026-27")).toBe("Form 138 (earlier 24Q)");
    expect(filingFormLabel("tds_26q", "Q1 2027-28")).toBe("Form 140 (earlier 26Q)");
  });

  it("keeps the old names for earlier periods and other forms", () => {
    expect(filingFormLabel("tds_24q", "Q4 2025-26")).toBe("TDS return 24Q (salaries)");
    expect(filingFormLabel("tds_26q", undefined)).toBe("TDS return 26Q (other payments)");
    expect(filingFormLabel("gstr_3b", "Q2 2026-27")).toBe("GSTR-3B");
  });
});
