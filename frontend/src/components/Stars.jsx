/**
 * Star ratings (MA17).
 *
 *   <Stars stars={4} />                      ★★★★☆   (screen readers: "4 out of 5 stars")
 *   <RatingSummary average={4.5} count={12} />   ★ 4.5 (12 ratings) · or "No ratings yet"
 */

// Five characters: filled stars first, then empty ones, e.g. 3 -> "★★★☆☆".
function starText(stars) {
  let text = "";
  for (let i = 1; i <= 5; i++) {
    if (i <= stars) {
      text = text + "★";
    } else {
      text = text + "☆";
    }
  }
  return text;
}

export function Stars({ stars }) {
  return (
    <span className="text-amber-500" role="img" aria-label={stars + " out of 5 stars"}>
      {starText(stars)}
    </span>
  );
}

// A CA's average rating and how many ratings it is based on.
export function RatingSummary({ average, count }) {
  if (!count) {
    return <span className="text-muted-foreground">No ratings yet</span>;
  }
  const word = count === 1 ? "rating" : "ratings";
  return (
    <span>
      <span className="text-amber-500">★</span> {average} ({count} {word})
    </span>
  );
}
