/**
 * Showing rupee amounts. The API sends money as strings like "2500.00".
 *
 *   formatRupees("2500.00")  -> "₹2,500"
 *   formatRupees("99.50")    -> "₹99.50"
 */

// Indian digit grouping (₹1,00,000); paise only when there are some.
export function formatRupees(amount) {
  const number = Number(amount);
  if (Number.isInteger(number)) {
    return "₹" + number.toLocaleString("en-IN");
  }
  return (
    "₹" + number.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

// The typical price range of a catalog service (GET /api/v1/marketplace/services),
// e.g. "₹600 – ₹1,000, median ₹700 (3 CAs)". The API sends no range until
// enough CAs offer the service.
export function typicalRangeText(service) {
  if (service.median_price === null) {
    return "Not enough data yet";
  }
  return (
    formatRupees(service.min_price) +
    " – " +
    formatRupees(service.max_price) +
    ", median " +
    formatRupees(service.median_price) +
    " (" +
    service.ca_count +
    " CAs)"
  );
}

// Where a price sits against the median of all CAs, or null if there is no median yet.
export function comparedToMedian(price, median) {
  if (median === null || median === undefined) {
    return null;
  }
  if (Number(price) < Number(median)) {
    return "Below the median";
  }
  if (Number(price) > Number(median)) {
    return "Above the median";
  }
  return "At the median";
}
