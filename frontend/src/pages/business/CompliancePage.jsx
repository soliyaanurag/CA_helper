import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { useFilings } from "@/api/compliance";
import { StatusBadge } from "@/components/StatusBadge";
import { daysLeftText, daysUntil, formatDate, monthLabel } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";

// The filter chips: which forms each one keeps.
const FORM_FILTERS = {
  All: null,
  GST: ["gstr_1", "gstr_3b", "cmp_08", "gstr_4"],
  TDS: ["tds_24q", "tds_26q"],
  ITR: ["itr"],
};
const DONE = ["filed", "filed_verified"];
const STATUS_FILTERS = {
  All: () => true,
  Upcoming: (item) => !DONE.includes(item.status) && daysUntil(item.due_date) >= 0,
  Overdue: (item) => !DONE.includes(item.status) && daysUntil(item.due_date) < 0,
};

/**
 * /business/compliance: every filing of this financial year.
 * Filings whose due date has passed come first, in "Earlier this year"; the rest are
 * grouped by the month they are due, soonest first. Chips filter by form and status.
 */
export function CompliancePage() {
  const filings = useFilings();
  const [formFilter, setFormFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");

  let content;
  if (filings.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (filings.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(filings.error)}
      </p>
    );
  } else if (filings.data === null) {
    content = (
      <p className="text-sm">
        <Link to="/business/onboarding" className="underline">
          Register your business
        </Link>{" "}
        to see which filings apply to you and when they are due.
      </p>
    );
  } else if (filings.data.length === 0) {
    content = (
      <p className="text-sm text-muted-foreground">No filings due for the rest of this year.</p>
    );
  } else {
    const forms = FORM_FILTERS[formFilter];
    const shown = filings.data.filter(
      (item) =>
        (forms === null || forms.includes(item.form_code)) && STATUS_FILTERS[statusFilter](item),
    );
    content = (
      <>
        <div className="flex flex-wrap gap-4">
          <Chips
            name="Form"
            options={Object.keys(FORM_FILTERS)}
            value={formFilter}
            onChange={setFormFilter}
          />
          <Chips
            name="Status"
            options={Object.keys(STATUS_FILTERS)}
            value={statusFilter}
            onChange={setStatusFilter}
          />
        </div>
        {shown.length === 0 ? (
          <p className="text-sm text-muted-foreground">No filings match these filters.</p>
        ) : (
          <FilingSections filings={shown} />
        )}
      </>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compliance calendar</h1>
      {content}
    </div>
  );
}

// A row of toggle buttons; exactly one is on.
function Chips({ name, options, value, onChange }) {
  return (
    <div role="group" aria-label={name} className="flex flex-wrap items-center gap-1">
      <span className="text-sm text-muted-foreground">{name}:</span>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={
            "rounded-full border px-3 py-0.5 text-sm " +
            (value === option
              ? "border-primary bg-primary text-primary-foreground"
              : "hover:bg-muted")
          }
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function FilingSections({ filings }) {
  const earlier = filings.filter((item) => daysUntil(item.due_date) < 0);
  // {"October 2026": [filings]}, in due-date order (the API sends them soonest first).
  const byMonth = {};
  for (const item of filings) {
    if (daysUntil(item.due_date) >= 0) {
      const month = monthLabel(item.due_date);
      byMonth[month] = byMonth[month] || [];
      byMonth[month].push(item);
    }
  }

  return (
    <div className="space-y-8">
      {earlier.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Earlier this year: due dates already passed</h2>
          <p className="text-sm text-muted-foreground">
            If you already filed this, you'll be able to mark it as filed.
          </p>
          <FilingTable filings={earlier} />
        </section>
      )}
      {Object.entries(byMonth).map(([month, items]) => (
        <section key={month} className="space-y-2">
          <h2 className="text-lg font-semibold">{month}</h2>
          <FilingTable filings={items} />
        </section>
      ))}
    </div>
  );
}

function FilingTable({ filings }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b text-muted-foreground">
          <tr>
            <th className="py-2 pr-4 font-medium">Form</th>
            <th className="py-2 pr-4 font-medium">Period</th>
            <th className="py-2 pr-4 font-medium">Due date</th>
            <th className="py-2 pr-4 font-medium">Days left</th>
            <th className="py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {filings.map((item) => (
            <tr key={item.id} className="border-b">
              <td className="py-2 pr-4">{label(FORM_LABELS, item.form_code)}</td>
              <td className="py-2 pr-4">{item.period_label}</td>
              <td className="py-2 pr-4">{formatDate(item.due_date)}</td>
              <td className="py-2 pr-4 tabular-nums">
                {DONE.includes(item.status) ? "—" : daysLeftText(item.due_date)}
              </td>
              <td className="py-2">
                <StatusBadge status={item.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
