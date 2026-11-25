"""Validate a country's Unity Catalog tables before (or after) onboarding it.

    python scripts/check_country.py GIN            # read the tables, resolve columns, report
    python scripts/check_country.py GIN --describe # also print DESCRIBE TABLE output

Reports: resolved hierarchy/year/score/context columns, years and unit counts,
missing score columns, boundary decode and match rates. Writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import countries  # noqa: E402
from services import assemble, databricks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iso3")
    parser.add_argument("--describe", action="store_true")
    args = parser.parse_args()
    country = countries.BY_ISO3.get(args.iso3.upper())
    if not country:
        print(f"{args.iso3}: add countries/{args.iso3.lower()}.py and register it in countries/__init__.py first.")
        return 2
    if not databricks.configured():
        print("Set DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET.")
        return 2
    problems = 0
    for role, table in country.tables.items():
        exists = databricks.table_exists(table)
        print(f"[{'ok' if exists else 'FAIL'}] {role:<11} {databricks.table_name(table)}")
        problems += not exists
        if exists and args.describe:
            print(databricks.query("DESCRIBE TABLE IDENTIFIER(:t)", {"t": databricks.table_name(table)}).to_string(index=False))
    if problems:
        return 1
    scores = databricks.read_table(country.tables["scores"])
    cols = list(scores.columns)
    hierarchy = assemble._hierarchy_columns(country, cols)
    year = assemble.resolve(cols, country.source.year_candidates)
    print(f"scores: {len(scores)} rows · hierarchy {hierarchy} · year column {year}")
    missing = [key for key, column in assemble._score_columns(cols).items() if not column and key != "composite"]
    print(f"[{'ok' if not missing else 'WARN'}] score columns missing: {missing or 'none'}")
    print("context columns:", assemble._context_columns(country, cols))
    if year:
        print("units per year:", scores.groupby(year).size().to_dict())
    payload, geometry = assemble.from_databricks(country)
    mapped = len(geometry["features"])
    print(f"[{'ok' if mapped else 'FAIL'}] boundaries matched to units: {mapped} of {len(payload['units'])} · boundary-only: {payload['boundaryOnly']}")
    print(f"years: {payload['years']}")
    return 0 if mapped else 1


if __name__ == "__main__":
    raise SystemExit(main())
