import { describe, expect, it } from "vitest";

import { comparedToMedian, formatRupees, typicalRangeText } from "./money";

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
