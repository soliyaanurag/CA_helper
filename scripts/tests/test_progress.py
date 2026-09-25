"""Tests for scripts/progress.py: fixture Markdown in, expected counts out."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import progress  # noqa: E402

ALPHA = """# Alpha

## Tasks
- [x] ALP-01 · P0 · A · Done task
- [~] ALP-02 · P1 · A · Task in progress
- [ ] ALP-03 · P1 · B · Open task
- [X] ALP-04 · P1 · A · Uppercase X is malformed

  - [ ] indented lines are ignored
Some text that is not a task.
"""

BETA = """# Beta
- [x] BET-01 · P0 · C · Done task
- [ ] BET-02 · P2 · C · Open task
- [ ] ALP-03 · P3 · C · Duplicate ID
- [ ] BET-03 - P2 - C - wrong separators
"""

TEMPLATE = """# Template
- [ ] XXX-01 · P1 · A · Example line in the template is ignored
"""


def make_docs(tmp_path: Path) -> Path:
    (tmp_path / "alpha.md").write_text(ALPHA, encoding="utf-8")
    (tmp_path / "beta.md").write_text(BETA, encoding="utf-8")
    (tmp_path / "_TEMPLATE.md").write_text(TEMPLATE, encoding="utf-8")
    return tmp_path


def test_counts_per_phase_member_and_module(tmp_path):
    report = progress.parse_dir(make_docs(tmp_path))

    assert len(report.tasks) == 6
    phases = report.by_phase()
    assert (phases[0].total, phases[0].done, phases[0].percent) == (2, 2, 100)
    assert (phases[1].total, phases[1].in_progress, phases[1].todo) == (2, 1, 1)
    assert phases[2].todo == 1 and phases[3].todo == 1

    owners = report.by_owner()
    assert (owners["A"].total, owners["A"].done) == (2, 1)
    assert owners["B"].total == 1
    assert (owners["C"].total, owners["C"].done) == (3, 1)

    modules = report.by_module()
    assert set(modules) == {"alpha", "beta"}
    assert report.module_owners("alpha") == "A,B"


def test_in_progress_and_current_phase(tmp_path):
    report = progress.parse_dir(make_docs(tmp_path))

    assert [t.id for t in report.in_progress()] == ["ALP-02"]
    assert report.current_phase() == 1


def test_warnings_for_malformed_lines_and_duplicates(tmp_path):
    report = progress.parse_dir(make_docs(tmp_path))

    assert len(report.warnings) == 3
    assert any("alpha.md:7" in w and "malformed" in w for w in report.warnings)
    assert any("beta.md:5" in w and "malformed" in w for w in report.warnings)
    assert any("duplicate ID ALP-03" in w for w in report.warnings)


def test_markdown_output_and_strict_exit_code(tmp_path, capsys):
    docs = make_docs(tmp_path)

    assert progress.main(["--dir", str(docs), "--markdown"]) == 0
    output = capsys.readouterr().out
    assert "| Phase | Done | In progress | To do | Total | % done |" in output
    assert "| P0 | 2 | 0 | 0 | 2 | 100% |" in output
    assert "**Current phase: P1" in output

    assert progress.main(["--dir", str(docs), "--strict"]) == 1


def test_all_done_has_no_current_phase(tmp_path):
    (tmp_path / "done.md").write_text("- [x] DON-01 · P0 · A · Finished\n", encoding="utf-8")

    report = progress.parse_dir(tmp_path)

    assert report.current_phase() is None
    assert "all tasks done" in progress.render_text(report)
