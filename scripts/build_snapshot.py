"""Build the shipped data snapshot (data_snapshot/) before a deploy.

    python scripts/build_snapshot.py                     # from Databricks (needs DATABRICKS_*)
    python scripts/build_snapshot.py --from-legacy DIR   # from ldt-demo assets/data/<country>/ bundles
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import constants  # noqa: E402
import countries  # noqa: E402
from services import assemble, store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-legacy", type=Path, help="folder holding <slug>/analytics-data.json and municipalities.geojson")
    parser.add_argument("--out", type=Path, default=constants.SNAPSHOT_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.from_legacy:
        built = []
        for country in countries.REGISTRY:
            folder = args.from_legacy / country.slug
            if not (folder / "analytics-data.json").is_file():
                logging.warning("No legacy bundle for %s in %s", country.iso3, folder)
                continue
            payload, geometry = assemble.from_legacy(country, folder)
            store.write_country(country.iso3, payload, geometry, args.out)
            built.append(f"{country.iso3}: {len(payload['units'])} units, {len(geometry['features'])} boundaries, years {payload['years']}")
        store.write_shared({}, {}, args.out)
        print("\n".join(built))
        return 0

    result = store.warm(force=True, directory=args.out)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
