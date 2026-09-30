import { describe, expect, it } from "vitest";

import {
  comparedToMedian,
  filingFormLabel,
  formatRupees,
  gstinCheckCharacter,
  gstinError,
  label,
  typicalRangeText,
  USER_ROLE_LABELS,
} from "@/lib";

// --- gstin.test --------------------------------------------------------------------------------

// Synthetic GSTINs only (built with the algorithm), never real ones.
const VALID = "27ABCDE1234F1Z0";

describe("GSTIN checks (same rules as the backend)", () => {
  it("computes the check character", () => {
    expect(gstinCheckCharacter("27ABCDE1234F1Z")).toBe("0");
  });

  it("accepts a GSTIN that fits its PAN and state", () => {
    expect(gstinError(VALID, "ABCDE1234F", "Maharashtra", "27")).toBeNull();
  });

  it.each([
    ["27ABCDE1234F1Z5", "ABCDE1234F", "Maharashtra", "27", "its last character does not match"],
    [VALID, "ABCDE1234F", "Gujarat", "24", "the code of Gujarat is 24"],
    [VALID, "ABCDE9999F", "Maharashtra", "27", "does not match your PAN"],
  ])("explains what is wrong with %s", (gstin, pan, state, code, message) => {
    expect(gstinError(gstin, pan, state, code)).toContain(message);
  });
});

// --- labels.test -------------------------------------------------------------------------------

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

// --- money.test --------------------------------------------------------------------------------

describe("formatRupees", () => {
  it("uses Indian digit grouping and hides zero paise", () => {
    expect(formatRupees("2500.00")).toBe("₹2,500");
    expect(formatRupees("150000.00")).toBe("₹1,50,000");
    expect(formatRupees("99.5")).toBe("₹99.50");
  });
});

describe("typicalRangeText", () => {
  it("describes the range, or says there is not enough data", () => {
    const service = {
      ca_count: 4,
      min_price: "500.00",
      median_price: "700.00",
      max_price: "900.00",
    };
    expect(typicalRangeText(service)).toBe("₹500 – ₹900, median ₹700 (4 CAs)");
    expect(typicalRangeText({ ...service, median_price: null })).toBe("Not enough data yet");
  });
});

describe("comparedToMedian", () => {
  it("places a price against the median", () => {
    expect(comparedToMedian("600", "700.00")).toBe("Below the median");
    expect(comparedToMedian("700", "700.00")).toBe("At the median");
    expect(comparedToMedian("800", "700.00")).toBe("Above the median");
    expect(comparedToMedian("800", null)).toBeNull();
  });
});
