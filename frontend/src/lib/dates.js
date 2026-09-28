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

const MILLISECONDS_PER_MINUTE = 60 * 1000;
const MILLISECONDS_PER_DAY = 24 * 60 * MILLISECONDS_PER_MINUTE;

// Today's date as "2026-09-27", in the browser's own time zone (people use the app in India).
export function todayIso() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

// Whole days from today to a date: 0 today, negative once it has passed.
export function daysUntil(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const [nowYear, nowMonth, nowDay] = todayIso().split("-").map(Number);
  const milliseconds = Date.UTC(year, month - 1, day) - Date.UTC(nowYear, nowMonth - 1, nowDay);
  return Math.round(milliseconds / MILLISECONDS_PER_DAY);
}

// "Today", "In 1 day", "In 12 days", "3 days ago".
export function daysLeftText(isoDate) {
  const days = daysUntil(isoDate);
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "In 1 day";
  }
  if (days > 1) {
    return "In " + days + " days";
  }
  if (days === -1) {
    return "1 day ago";
  }
  return -days + " days ago";
}

// "2026-10-13" -> "October 2026".
export function monthLabel(isoDate) {
  const [year, month] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
}

// How long until a moment, for request deadlines: "expires in 31 h", "expires in 20 min".
export function expiresInText(isoTimestamp) {
  const minutes = Math.floor((new Date(isoTimestamp) - new Date()) / MILLISECONDS_PER_MINUTE);
  if (minutes <= 0) {
    // The worker marks the request "expired" within 15 minutes; until then it is still requested.
    return "answer time over";
  }
  if (minutes < 60) {
    return "expires in " + minutes + " min";
  }
  return "expires in " + Math.floor(minutes / 60) + " h";
}

// True once a moment (e.g. a request's answer deadline) has passed.
export function isPast(isoTimestamp) {
  return new Date(isoTimestamp) <= new Date();
}
