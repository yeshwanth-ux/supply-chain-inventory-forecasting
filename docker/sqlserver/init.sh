#!/usr/bin/env bash
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd
if [[ ! -x "$SQLCMD" ]]; then SQLCMD=/opt/mssql-tools/bin/sqlcmd; fi

for attempt in {1..30}; do
  if "$SQLCMD" -S sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -Q "SELECT 1" >/dev/null 2>&1; then
    "$SQLCMD" -S sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -b -v DatabaseName="$SQLSERVER_DATABASE" -i /schema.sql
    "$SQLCMD" -S sqlserver -U sa -P "$SQLSERVER_PASSWORD" -C -b -v DatabaseName="$SQLSERVER_DATABASE" -i /views.sql
    exit 0
  fi
  sleep 2
done

echo "SQL Server did not become ready" >&2
exit 1
