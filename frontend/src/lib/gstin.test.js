import { describe, expect, it } from "vitest";

import { gstinCheckCharacter, gstinError } from "./gstin";

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
