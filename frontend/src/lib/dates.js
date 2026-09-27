/**
 * Showing dates. The API sends dates as "2026-09-20" and times as UTC timestamps
 * ("2026-09-27T10:30:00+00:00"); people in India see them in Indian time.
 *
 *   formatDate("2026-09-20")               -> "20 Sept 2026"
 *   formatDateTime("2026-09-27T10:30:00Z") -> "27 Sept 2026, 4:00 pm"
 */

// A plain date. It is built from its parts, so no time zone can move it to the day before.
export function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// A moment in time, shown in Indian time.
export function formatDateTime(isoTimestamp) {
  return new Date(isoTimestamp).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}
