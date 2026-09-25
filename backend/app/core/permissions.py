"""Access control helpers. Not built yet.

Planned:
- role decorators, e.g. `@role_required("business")`, used on EVERY endpoint
- `ca_has_active_access(ca_id, business_id)`: the only way a CA may read a
  business's data (true only while an engagement or approved invite is active)
"""
