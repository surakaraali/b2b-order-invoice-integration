"""Run every SQL file in sql/ in order with DuckDB and save the results for the report site.

Usage, from the repository root:
    python scripts/run_sql.py

Input:  data/raw/*.csv (create them with: python data/generate_data.py)
Output: docs/data/results.json, one entry per SQL file with the query text and its result rows
"""
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
OUTPUT = ROOT / "docs" / "data" / "results.json"


def to_json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    raise TypeError(f"Cannot serialise {type(value).__name__}")


def main():
    os.chdir(ROOT)                      # the CSV paths inside the SQL files are relative to the repository root
    con = duckdb.connect()              # in-memory database: nothing is written to disk
    results = {}
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        query = sql_file.read_text(encoding="utf-8")
        if sql_file.name.startswith("00_"):
            con.execute(query)
            tables = con.execute("SELECT count(*) FROM duckdb_tables()").fetchone()[0]
            print(f"{sql_file.name:36} -> {tables} tables loaded")
            continue
        cursor = con.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        name = sql_file.stem.split("_", 1)[1]
        results[name] = {"file": f"sql/{sql_file.name}", "sql": query.strip(), "columns": columns, "rows": rows}
        print(f"{sql_file.name:36} -> {len(rows)} rows")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=to_json) + "\n", encoding="utf-8")
    print(f"\nSaved {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
