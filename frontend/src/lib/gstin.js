/**
 * GSTIN checks, the same as backend/app/utils/gstin.py (and the same messages).
 *
 *   gstinError("27ABCDE1234F1Z0", "ABCDE1234F", "27")   -> null (fine)
 *
 * A GSTIN is <state code 2><PAN 10><entity 1>Z<check character 1>. The check character
 * comes from the other 14: each character's value (0-9, A-Z = 0-35) is multiplied by
 * 1 and 2 in turn, the base-36 digits of the products are added up, and the check
 * character makes the total a multiple of 36.
 */

const CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export function gstinCheckCharacter(first14) {
  let total = 0;
  for (let index = 0; index < first14.length; index++) {
    const product = CHARACTERS.indexOf(first14[index]) * (index % 2 === 0 ? 1 : 2);
    total += Math.floor(product / 36) + (product % 36);
  }
  return CHARACTERS[(36 - (total % 36)) % 36];
}

/** What is wrong with a well-formed GSTIN for this PAN and state (name + code), or null. */
export function gstinError(gstin, pan, stateName, stateCode) {
  if (gstinCheckCharacter(gstin.slice(0, 14)) !== gstin[14]) {
    return "This GSTIN is not valid: its last character does not match. Check for a typo.";
  }
  if (stateCode && gstin.slice(0, 2) !== stateCode) {
    return `This GSTIN starts with ${gstin.slice(0, 2)}, but the code of ${stateName} is ${stateCode}.`;
  }
  if (pan && gstin.slice(2, 12) !== pan) {
    return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN.";
  }
  return null;
}
