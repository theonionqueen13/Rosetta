"""Create required Supabase tables for the Rosetta app.

This script reads the Postgres connection settings from `.streamlit/secrets.toml`
(and/or the existing `postgres` section) and executes the SQL in
`supabase_setup.sql` to create the `user_profiles` and `user_admins` tables
with RLS policies.

Usage:
    python scripts/setup_supabase_schema.py

Optional: pass a user_id to insert as an admin:
    python scripts/setup_supabase_schema.py --admin <USER_ID>
"""

import argparse
from pathlib import Path

import psycopg2
import toml


def load_secrets(path: Path) -> dict:
    return toml.loads(path.read_text())


def get_postgres_conn(secrets: dict):
    pg = secrets.get("postgres") or {}
    return psycopg2.connect(
        host=pg.get("host", "localhost"),
        port=pg.get("port", 5432),
        dbname=pg.get("database", "postgres"),
        user=pg.get("user"),
        password=pg.get("password"),
    )


def run_sql(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Run Supabase schema setup SQL.")
    parser.add_argument(
        "--secrets",
        default=".streamlit/secrets.toml",
        help="Path to streamlit secrets.toml",
    )
    parser.add_argument(
        "--admin",
        help="Optional user_id to insert into user_admins after creating the table",
    )
    args = parser.parse_args()

    secrets_path = Path(args.secrets)
    if not secrets_path.exists():
        raise SystemExit(f"Secrets file not found: {secrets_path}")

    secrets = load_secrets(secrets_path)
    conn = get_postgres_conn(secrets)

    sql_path = Path(__file__).resolve().parents[1] / "supabase_setup.sql"
    if not sql_path.exists():
        raise SystemExit(f"Cannot find supabase_setup.sql at {sql_path}")

    print(f"Running SQL from: {sql_path}")
    run_sql(conn, sql_path.read_text())
    print("✅ Schema setup complete.")

    if args.admin:
        print(f"Adding admin user_id={args.admin}")
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.user_admins (user_id) values (%s) on conflict do nothing;",
                (args.admin,),
            )
        conn.commit()
        print("✅ Admin user inserted.")

    conn.close()


if __name__ == "__main__":
    main()
