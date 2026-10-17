# File: data/provision_postgres.py
# History: Version 0.3, October 17, 2026
# Program: Create or update the least-privilege PostgreSQL login used by the API container.
# Input: An administrator DATABASE_URL plus APP_DATABASE_USER and APP_DATABASE_PASSWORD values.
# Processing: Validate credentials, safely compose role DDL, and grant only review/API table permissions.
# Output: A reusable application role without database-owner or superuser privileges.
"""Provision the restricted database role used by the running API."""
from __future__ import annotations

import os
import re

import psycopg
from psycopg import sql


def provision(database_url: str, username: str, password: str) -> None:
    """Create or update a login role and grant only the permissions the API needs."""
    # Restrict role names and require a sufficiently long local secret before using admin access.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", username):
        raise ValueError("APP_DATABASE_USER must be a simple PostgreSQL role name")
    if len(password) < 32:
        raise ValueError("APP_DATABASE_PASSWORD must contain at least 32 characters")

    with psycopg.connect(database_url) as connection:
        # Use psycopg's SQL composition objects so credentials are never concatenated into DDL.
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (username,)
        ).fetchone()
        action = "ALTER ROLE" if exists else "CREATE ROLE"
        connection.execute(
            sql.SQL("{} {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION").format(
                sql.SQL(action), sql.Identifier(username), sql.Literal(password)
            )
        )

        # Ensure a hardened database still allows this app role to connect and resolve public tables.
        database_name = connection.execute("SELECT current_database()").fetchone()[0]
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name), sql.Identifier(username)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(username))
        )

        # Grant reads needed for review summaries, plus writes only to review state and proposal status.
        connection.execute(
            sql.SQL("GRANT SELECT ON problem_proposals TO {}").format(sql.Identifier(username))
        )
        connection.execute(
            sql.SQL("GRANT UPDATE (status) ON problem_proposals TO {}").format(sql.Identifier(username))
        )
        connection.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE ON proposal_reviews TO {}").format(sql.Identifier(username))
        )


def main() -> None:
    """Read the setup credentials from the container environment and provision the role."""
    # The admin connection is available only to this short-lived setup service in Compose.
    database_url = os.environ.get("DATABASE_URL", "")
    username = os.environ.get("APP_DATABASE_USER", "")
    password = os.environ.get("APP_DATABASE_PASSWORD", "")
    if not all((database_url, username, password)):
        raise SystemExit("Set DATABASE_URL, APP_DATABASE_USER, and APP_DATABASE_PASSWORD")
    provision(database_url, username, password)


if __name__ == "__main__":
    main()
