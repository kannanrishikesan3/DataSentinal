"""Intentionally empty.

The original plan was a repository layer between `services/` and the ORM
models, but with SQLAlchemy 2.0's `select()`/`Session` API already reading
as a thin, explicit query builder, every service module
(`services/scans.py`, `services/dashboard.py`, `services/audit.py`, ...)
queries `models/` directly — an extra repository indirection layer would
have wrapped each query in a pass-through method without adding real
behavior. Revisit this if query logic starts duplicating across services.
"""
