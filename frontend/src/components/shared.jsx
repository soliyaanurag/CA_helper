import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router";

import {
  errorMessage,
  markAllNotificationsRead,
  markNotificationRead,
  NOTIFICATIONS_KEY,
  useNotifications,
  useUnreadCount,
} from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  cn,
  COMPLIANCE_STATUS_LABELS,
  ENGAGEMENT_STATUS_LABELS,
  ENTITY_TYPE_LABELS,
  expiresInText,
  filingFormLabel,
  FORM_LABELS,
  formatDate,
  formatDateTime,
  formatRupees,
  GST_SCHEME_LABELS,
  label,
} from "@/lib";

// --- FormField ---------------------------------------------------------------------------------

/**
 * A labelled input with its validation message, for React Hook Form:
 *
 *   <FormField id="email" label="Email" type="email" error={errors.email} {...register("email")} />
 *
 * `hint` is shown under the input while there is no error. The error is linked to the
 * input (aria-describedby), so screen readers read it with the field.
 */
export function FormField({ id, label, error, hint, ...inputProps }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? id + "-error" : undefined}
        {...inputProps}
      />
      {error ? (
        <p id={id + "-error"} className="text-sm text-destructive">
          {error.message}
        </p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

// --- FormCard ----------------------------------------------------------------------------------

/** A small centred card holding one form: login, signup, passwords. */
export function FormCard({ title, description, children }) {
  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader>
        <CardTitle>
          <h1 className="text-xl font-semibold">{title}</h1>
        </CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

// --- StatusBadge -------------------------------------------------------------------------------

// A colour per filing status, so what needs attention stands out.
const COLOURS = {
  overdue: "bg-red-100 text-red-900",
  docs_pending: "bg-amber-100 text-amber-900",
  ready: "bg-sky-100 text-sky-900",
  with_ca: "bg-violet-100 text-violet-900",
  filed: "bg-green-100 text-green-900",
  filed_verified: "bg-green-100 text-green-900",
};

/** A filing's status (compliance_items.status) as a coloured badge. */
export function StatusBadge({ status }) {
  return (
    <Badge variant="secondary" className={COLOURS[status]}>
      {label(COMPLIANCE_STATUS_LABELS, status)}
    </Badge>
  );
}

// --- Stars -------------------------------------------------------------------------------------

/**
 * Star ratings.
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

// --- Markdown ----------------------------------------------------------------------------------

// Styles for the HTML that Markdown produces (headings, lists, links), written as
// Tailwind "child" selectors so each piece looks like the rest of the app.
const STYLES = [
  "space-y-3 text-sm leading-relaxed",
  "[&_h1]:text-lg [&_h1]:font-semibold",
  "[&_h2]:mt-5 [&_h2]:font-semibold",
  "[&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5",
  "[&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-5",
  "[&_a]:text-primary [&_a]:underline-offset-4 [&_a]:hover:underline",
].join(" ");

/** Shows a Markdown text (e.g. a form's explanation from content/forms/) as formatted text. */
export function Markdown({ children }) {
  return (
    <div className={STYLES}>
      <ReactMarkdown
        components={{
          // Links to official portals open in a new tab.
          a: ({ href, children: text }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {text}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

// --- EngagementCard ----------------------------------------------------------------------------

// Badge colour for each engagement status.
const STATUS_COLORS = {
  requested: "bg-amber-100 text-amber-800",
  quoted: "bg-blue-100 text-blue-800",
  active: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-700",
  declined: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-700",
  cancelled: "bg-gray-100 text-gray-700",
};

// Adds up one kind of price of all filings ("listed_price", "quoted_price" or "agreed_price").
function total(items, priceName) {
  let sum = 0;
  for (const item of items) {
    sum = sum + Number(item[priceName]);
  }
  return sum;
}

// The steps shown for each status, e.g. Requested → Active → Completed.
function stepsFor(status) {
  if (status === "quoted") {
    return ["requested", "quoted", "active", "completed"];
  }
  if (status === "declined" || status === "expired" || status === "cancelled") {
    return ["requested", status];
  }
  return ["requested", "active", "completed"];
}

// How a step looks: bold for the current one, grey for done ones, lighter for the rest.
function stepClass(index, current) {
  if (index === current) {
    return "font-semibold";
  }
  if (index < current) {
    return "text-muted-foreground";
  }
  return "text-muted-foreground/60";
}

// ✓ for a done step, ● for the current one, ○ for one still to come.
function stepMark(index, current) {
  if (index < current) {
    return "✓ ";
  }
  if (index === current) {
    return "● ";
  }
  return "○ ";
}

/** Where the engagement is: ✓ done steps, ● the current one (bold), ○ steps still to come. */
function Timeline({ status }) {
  const steps = stepsFor(status);
  const current = steps.indexOf(status);
  return (
    <ol aria-label="Progress" className="flex flex-wrap items-center gap-1 text-xs">
      {steps.map((step, index) => (
        <li
          key={step}
          aria-current={index === current ? "step" : undefined}
          className={stepClass(index, current)}
        >
          {index > 0 && <span aria-hidden="true">→ </span>}
          {stepMark(index, current)}
          {label(ENGAGEMENT_STATUS_LABELS, step)}
        </li>
      ))}
    </ol>
  );
}

/**
 * One engagement as a card: who it is with, its status, and each filing with its
 * prices. Used by the business's and the CA's "My engagements" pages. `title` is
 * the other side's name; `children` are the action buttons for the current status.
 */
export function EngagementCard({ engagement, title, children }) {
  const items = engagement.items;
  const hasQuote = items.length > 0 && items[0].quoted_price !== null;
  const hasAgreed = items.length > 0 && items[0].agreed_price !== null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h3>{title}</h3>
          {engagement.is_pro_bono && (
            <Badge className="bg-purple-100 text-purple-800">Pro-bono</Badge>
          )}
          <Badge className={STATUS_COLORS[engagement.status]}>
            {label(ENGAGEMENT_STATUS_LABELS, engagement.status)}
          </Badge>
        </CardTitle>
        <CardDescription>
          Requested {formatDateTime(engagement.requested_at)}
          {isWaiting(engagement) && (
            <span className="font-medium text-amber-800">
              {" "}
              · {expiresInText(engagement.expires_at)}
            </span>
          )}
        </CardDescription>
        <Timeline status={engagement.status} />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <table className="w-full text-left">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">Filing</th>
              <th className="py-1 pr-3 font-medium">Service</th>
              <th className="py-1 pr-3 font-medium">Listed price</th>
              {hasQuote && <th className="py-1 pr-3 font-medium">Quoted price</th>}
              {hasAgreed && <th className="py-1 font-medium">Agreed price</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b">
                <td className="py-1 pr-3">
                  {item.form_code
                    ? filingFormLabel(item.form_code, item.period_label)
                    : "Removed filing"}{" "}
                  {item.period_label}
                  {item.due_date && (
                    <span className="text-muted-foreground">
                      {" "}
                      · due {formatDate(item.due_date)}
                    </span>
                  )}
                </td>
                <td className="py-1 pr-3">{item.service_name}</td>
                <td className="py-1 pr-3">{formatRupees(item.listed_price)}</td>
                {hasQuote && <td className="py-1 pr-3">{formatRupees(item.quoted_price)}</td>}
                {hasAgreed && <td className="py-1">{formatRupees(item.agreed_price)}</td>}
              </tr>
            ))}
          </tbody>
          <tfoot className="font-medium">
            <tr>
              <td className="py-1 pr-3" colSpan={2}>
                Total
              </td>
              <td className="py-1 pr-3">{formatRupees(total(items, "listed_price"))}</td>
              {hasQuote && (
                <td className="py-1 pr-3">{formatRupees(total(items, "quoted_price"))}</td>
              )}
              {hasAgreed && <td className="py-1">{formatRupees(total(items, "agreed_price"))}</td>}
            </tr>
          </tfoot>
        </table>
        {engagement.quote_reason && (
          <p>
            <span className="font-medium">Reason for the quote: </span>
            {engagement.quote_reason}
          </p>
        )}
        {engagement.rating && (
          <p>
            <span className="font-medium">Rating: </span>
            <Stars stars={engagement.rating.stars} />
            {engagement.rating.review && <span> “{engagement.rating.review}”</span>}
          </p>
        )}
        {children}
      </CardContent>
    </Card>
  );
}

// True while a request waits for the CA's answer and has a deadline ("expires in 31 h").
// Only requests expire; a quote waits for the business without a deadline.
function isWaiting(engagement) {
  return engagement.status === "requested" && Boolean(engagement.expires_at);
}

// --- NotificationBell --------------------------------------------------------------------------

/**
 * The bell in the sidebar (every role): the number of unread notifications, and a
 * tray with the latest 10 when clicked. Clicking an entry marks it read and opens its
 * page; "Mark all read" clears the count.
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const count = unread.data?.unread ?? 0;

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="relative"
      >
        <BellIcon />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-5 rounded-full bg-red-600 px-1 text-center text-xs text-white tabular-nums">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </Button>
      {open && <Tray onClose={() => setOpen(false)} hasUnread={count > 0} />}
    </div>
  );
}

function Tray({ onClose, hasUnread }) {
  const notifications = useNotifications(true);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
  }

  async function openEntry(entry) {
    setError(null);
    try {
      if (entry.read_at === null) await markNotificationRead(entry.id);
      refresh();
      onClose();
      if (entry.link) navigate(entry.link);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  async function markAll() {
    setError(null);
    try {
      await markAllNotificationsRead();
      refresh();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Notifications"
      className="absolute top-full left-0 z-50 mt-2 w-80 rounded-md border bg-background shadow-lg"
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <p className="text-sm font-medium">Notifications</p>
        {hasUnread && (
          <Button variant="link" size="sm" className="h-auto p-0" onClick={markAll}>
            Mark all read
          </Button>
        )}
      </div>
      {notifications.isPending && <p className="p-3 text-sm text-muted-foreground">Loading...</p>}
      {notifications.isError && (
        <p role="alert" className="p-3 text-sm text-destructive">
          {errorMessage(notifications.error)}
        </p>
      )}
      {error && (
        <p role="alert" className="px-3 pt-2 text-sm text-destructive">
          {error}
        </p>
      )}
      {notifications.isSuccess && notifications.data.items.length === 0 && (
        <p className="p-3 text-sm text-muted-foreground">No notifications yet.</p>
      )}
      {notifications.isSuccess && notifications.data.items.length > 0 && (
        <ul className="max-h-96 divide-y overflow-y-auto">
          {notifications.data.items.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => openEntry(entry)}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm hover:bg-muted",
                  entry.read_at === null && "bg-sky-50",
                )}
              >
                <span className={cn("block", entry.read_at === null && "font-medium")}>
                  {entry.title}
                </span>
                <span className="block text-xs text-muted-foreground">{entry.body}</span>
                <span className="block text-xs text-muted-foreground">
                  {formatDateTime(entry.created_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

// --- RegulatoryChangeCard ----------------------------------------------------------------------

const CHANGE_TYPE_LABELS = {
  due_date_extension: "Due date extension",
  rate_change: "Rate change",
  new_rule: "New rule",
  other: "Other",
};

// "GSTR-3B, GSTR-1"
function formsText(formCodes) {
  const names = [];
  for (const code of formCodes) {
    names.push(label(FORM_LABELS, code));
  }
  return names.join(", ");
}

// Who the change is for, e.g. "GST scheme: Regular (QRMP) · States: Maharashtra".
function whoText(affected) {
  const parts = [];
  if (affected.gst_schemes) {
    const names = [];
    for (const code of affected.gst_schemes) names.push(label(GST_SCHEME_LABELS, code));
    parts.push("GST scheme: " + names.join(", "));
  }
  if (affected.entity_types) {
    const names = [];
    for (const code of affected.entity_types) names.push(label(ENTITY_TYPE_LABELS, code));
    parts.push("Business type: " + names.join(", "));
  }
  if (affected.states) {
    parts.push("States: " + affected.states.join(", "));
  }
  if (parts.length === 0) {
    return "Everyone with an open filing of these forms";
  }
  return parts.join(" · ");
}

/**
 * One change found in the news, with its article (the admin page and the Regulatory
 * updates page). `children` is shown at the bottom.
 */
export function RegulatoryChangeCard({ change, children }) {
  const dates = change.dates;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{label(CHANGE_TYPE_LABELS, change.change_type)}</Badge>
          <Badge variant="secondary">{formsText(change.form_codes)}</Badge>
          {change.affected_categories.extracted_by === "keywords" && (
            <Badge variant="outline">Found by keywords: read the article</Badge>
          )}
        </div>
        <CardTitle className="pt-2 text-base">{change.summary}</CardTitle>
        <CardDescription>
          From{" "}
          <a href={change.article_url} target="_blank" rel="noreferrer" className="underline">
            {change.article_title}
          </a>{" "}
          ({change.source_name}
          {change.published_at ? ", " + formatDateTime(change.published_at) : ""})
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="grid gap-1 sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">For</dt>
          <dd>{whoText(change.affected_categories)}</dd>
          {dates.period && (
            <>
              <dt className="text-muted-foreground">Period</dt>
              <dd>{dates.period}</dd>
            </>
          )}
          {dates.old_due_date && (
            <>
              <dt className="text-muted-foreground">Old due date</dt>
              <dd>{formatDate(dates.old_due_date)}</dd>
            </>
          )}
          {dates.new_due_date && (
            <>
              <dt className="text-muted-foreground">New due date</dt>
              <dd>{formatDate(dates.new_due_date)}</dd>
            </>
          )}
        </dl>
        {children}
      </CardContent>
    </Card>
  );
}
