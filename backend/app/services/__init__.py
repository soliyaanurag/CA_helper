"""Business logic, one file per feature (auth_service.py, compliance_service.py, ...).

Routes call these functions; they never query the database themselves. When one
feature needs another feature's data, it calls that feature's service function
instead of querying its models (CLAUDE.md rule 9).

Each public function is one unit of work: it validates, changes data and commits
once at its end (or raises ApiError before committing). Helpers that other
functions compose do not commit; their docstrings say so.
"""
