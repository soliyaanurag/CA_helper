"""Business logic for the alerts module. None yet.

Functions here are the module's public interface: routes call them, and other
modules may call the ones listed under "Service functions other modules call" in
docs/modules/alerts.md.

Each public function is one unit of work: it validates, changes data and commits
once at its end (or raises ApiError before committing). Helpers that other
functions compose do not commit; their docstrings say so.
"""
