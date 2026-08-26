#!/usr/bin/env python3
"""Bootstrap script: creates the first organization + admin user.

There is deliberately no public signup endpoint (spec section 40 — roles
are admin-provisioned, not self-service), which means a fresh deployment
has no way into the dashboard at all until *something* creates the first
admin directly against the database. This is that something — run it once
per new organization, typically right after `alembic upgrade head`.

Usage:
    python scripts/create_org_admin.py \\
        --org "Acme Corp" \\
        --email admin@acme-corp.example.com \\
        --password 'correct horse battery staple'

Safe to re-run: an existing organization (matched by name) or user (matched
by email) is reused rather than duplicated, so this can also double as an
idempotent "ensure this admin exists" step in automation.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from datasentinel_backend.core.database import get_engine, get_session_factory, init_db
from datasentinel_backend.models.models import Organization, User
from datasentinel_backend.security.passwords import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--org", required=True, help="Organization name (created if it doesn't exist)")
    parser.add_argument("--email", required=True, help="Admin user's email")
    parser.add_argument("--password", help="Admin password (omit to be prompted, safer than a shell arg)")
    parser.add_argument("--full-name", default=None)
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    engine = get_engine()
    init_db(engine)  # no-op if `alembic upgrade head` already created the schema
    session_factory = get_session_factory()
    session = session_factory()
    try:
        org = session.scalar(select(Organization).where(Organization.name == args.org))
        if org is None:
            org = Organization(id=uuid.uuid4(), name=args.org, created_at=datetime.now(timezone.utc))
            session.add(org)
            session.flush()
            print(f"Created organization '{args.org}' ({org.id})")
        else:
            print(f"Using existing organization '{args.org}' ({org.id})")

        user = session.scalar(select(User).where(User.email == args.email))
        if user is not None:
            if user.org_id != org.id:
                print(f"Error: {args.email} already exists in a different organization.", file=sys.stderr)
                return 1
            user.hashed_password = hash_password(password)
            user.role = "admin"
            user.is_active = True
            print(f"Updated existing user '{args.email}' to admin and reset their password.")
        else:
            user = User(
                id=uuid.uuid4(),
                org_id=org.id,
                email=args.email,
                hashed_password=hash_password(password),
                full_name=args.full_name,
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            print(f"Created admin user '{args.email}'.")

        session.commit()
    finally:
        session.close()

    print("\nLog in at the dashboard with these credentials, then create endpoints/enrollment from there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
