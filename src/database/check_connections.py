"""Check PostgreSQL and SQL Server connectivity from configured environment values."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from src.database.postgres import check_connection as check_postgres
from src.database.sqlserver import check_connection as check_sqlserver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=("postgres", "sqlserver", "both"), default="both")
    args = parser.parse_args()
    load_dotenv()

    checks = {
        "postgres": check_postgres,
        "sqlserver": check_sqlserver,
    }
    selected = checks if args.database == "both" else {args.database: checks[args.database]}
    for name, check in selected.items():
        if not check():
            raise SystemExit(f"{name} connection check failed")
        print(f"{name} connection successful")


if __name__ == "__main__":
    main()
