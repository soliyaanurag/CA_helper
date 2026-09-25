#!/usr/bin/env python3
"""Progress tracker: summarises the task lines in docs/modules/*.md.

A task line looks exactly like this (one per line, at the start of the line):

    - [ ] COM-02 · P1 · A · Calendar (month + list views) with item statuses

States: `[ ]` to do, `[~]` in progress, `[x]` done.

Usage (normally via make):
    make progress        ->  python scripts/progress.py
    make progress-md     ->  python scripts/progress.py --markdown
    python scripts/progress.py --strict   exit code 1 on malformed lines / duplicate IDs

Standard library only. The output is never committed: the module docs are the
single source of truth.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "docs" / "modules"

TASK_RE = re.compile(
    r"^- \[(?P<state>[ ~x])\] "  # checkbox
    r"(?P<id>[A-Z]+-\d+) · P(?P<phase>\d) · (?P<owner>[ABC]) · (?P<text>\S.*)$"
)
# Any top-level line that looks like a checkbox; if it does not match TASK_RE it is malformed.
CHECKBOX_RE = re.compile(r"^- \[.?\]")

STATE_LABELS = {" ": "to do", "~": "in progress", "x": "done"}


@dataclass(frozen=True)
class Task:
    id: str
    phase: int
    owner: str
    state: str  # " ", "~" or "x"
    text: str
    module: str  # file name without .md, e.g. "compliance"
    line: int


@dataclass
class Counts:
    total: int = 0
    done: int = 0
    in_progress: int = 0
    todo: int = 0

    def add(self, task: Task) -> None:
        self.total += 1
        if task.state == "x":
            self.done += 1
        elif task.state == "~":
            self.in_progress += 1
        else:
            self.todo += 1

    @property
    def percent(self) -> int:
        return round(100 * self.done / self.total) if self.total else 0


@dataclass
class Report:
    tasks: list[Task]
    warnings: list[str]

    def _group(self, key) -> dict:
        groups: dict = {}
        for task in self.tasks:
            groups.setdefault(key(task), Counts()).add(task)
        return dict(sorted(groups.items()))

    def by_phase(self) -> dict[int, Counts]:
        return self._group(lambda t: t.phase)

    def by_owner(self) -> dict[str, Counts]:
        return self._group(lambda t: t.owner)

    def by_module(self) -> dict[str, Counts]:
        return self._group(lambda t: t.module)

    def module_owners(self, module: str) -> str:
        return ",".join(sorted({t.owner for t in self.tasks if t.module == module}))

    def in_progress(self) -> list[Task]:
        return [t for t in self.tasks if t.state == "~"]

    def current_phase(self) -> int | None:
        """The lowest phase that still has open (not done) tasks."""
        open_phases = [t.phase for t in self.tasks if t.state != "x"]
        return min(open_phases) if open_phases else None


def parse_file(path: Path) -> tuple[list[Task], list[str]]:
    tasks, warnings = [], []
    module = path.stem
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.rstrip()
        match = TASK_RE.match(line)
        if match:
            tasks.append(
                Task(
                    id=match["id"],
                    phase=int(match["phase"]),
                    owner=match["owner"],
                    state=match["state"],
                    text=match["text"],
                    module=module,
                    line=number,
                )
            )
        elif CHECKBOX_RE.match(line):
            warnings.append(f"{path.name}:{number}: malformed task line: {line!r}")
    return tasks, warnings


def parse_dir(directory: Path) -> Report:
    """Parse every module doc. Files starting with "_" (the template) are skipped."""
    tasks, warnings = [], []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        file_tasks, file_warnings = parse_file(path)
        tasks.extend(file_tasks)
        warnings.extend(file_warnings)

    seen: dict[str, Task] = {}
    for task in tasks:
        if task.id in seen:
            first = seen[task.id]
            warnings.append(
                f"duplicate ID {task.id}: {first.module}.md:{first.line} and "
                f"{task.module}.md:{task.line}"
            )
        else:
            seen[task.id] = task
    return Report(tasks=tasks, warnings=warnings)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
HEADERS = ["Done", "In progress", "To do", "Total", "% done"]


def _row(counts: Counts) -> list[str]:
    return [
        str(counts.done),
        str(counts.in_progress),
        str(counts.todo),
        str(counts.total),
        f"{counts.percent}%",
    ]


def _tables(report: Report) -> list[tuple[str, list[str], list[list[str]]]]:
    """(title, headers, rows) for each summary table."""
    phase_rows = [[f"P{p}", *_row(c)] for p, c in report.by_phase().items()]
    owner_rows = [[f"Member {o}", *_row(c)] for o, c in report.by_owner().items()]
    module_rows = [[m, report.module_owners(m), *_row(c)] for m, c in report.by_module().items()]
    total = Counts()
    for task in report.tasks:
        total.add(task)
    phase_rows.append(["All", *_row(total)])
    return [
        ("Per phase", ["Phase", *HEADERS], phase_rows),
        ("Per member", ["Member", *HEADERS], owner_rows),
        ("Per module", ["Module", "Owner", *HEADERS], module_rows),
    ]


def _in_progress_lines(report: Report) -> list[str]:
    items = report.in_progress()
    if not items:
        return ["(none)"]
    return [f"{t.id} · P{t.phase} · {t.owner} · {t.text}  ({t.module}.md)" for t in items]


def _current_phase_line(report: Report) -> str:
    phase = report.current_phase()
    if phase is None:
        return "Current phase: all tasks done"
    return f"Current phase: P{phase} (lowest phase with open tasks)"


def render_text(report: Report) -> str:
    out = []
    for title, headers, rows in _tables(report):
        columns = zip(headers, *rows, strict=True)
        widths = [max(len(cell) for cell in column) for column in columns]
        out.append(title)
        out.append("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)))
        out.append("  " + "  ".join("-" * w for w in widths))
        for row in rows:
            out.append("  " + "  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)))
        out.append("")
    out.append("In progress [~]")
    out.extend(f"  {line}" for line in _in_progress_lines(report))
    out.append("")
    out.append(_current_phase_line(report))
    return "\n".join(out)


def render_markdown(report: Report) -> str:
    out = []
    for title, headers, rows in _tables(report):
        out.append(f"**{title}**")
        out.append("")
        out.append("| " + " | ".join(headers) + " |")
        out.append("|" + "|".join("---" for _ in headers) + "|")
        for row in rows:
            out.append("| " + " | ".join(row) + " |")
        out.append("")
    out.append("**In progress `[~]`**")
    out.append("")
    out.extend(f"- {line}" for line in _in_progress_lines(report))
    out.append("")
    out.append(f"**{_current_phase_line(report)}**")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--markdown", action="store_true", help="output Markdown tables")
    parser.add_argument("--strict", action="store_true", help="exit 1 if there are warnings")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="module docs folder")
    args = parser.parse_args(argv)

    report = parse_dir(args.dir)
    print(render_markdown(report) if args.markdown else render_text(report))
    for warning in report.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 1 if (args.strict and report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
