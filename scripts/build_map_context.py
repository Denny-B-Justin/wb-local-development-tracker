"""Build a country's map surroundings (neighbours + sea box) from Natural Earth 1:10m countries.

    curl -L -o /tmp/ne10.geojson \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson
    python scripts/build_map_context.py /tmp/ne10.geojson            # every registered country without a file
    python scripts/build_map_context.py /tmp/ne10.geojson --only GIN # one country, overwriting

Writes assets/geo/context/<slug>.json (public-domain data; no service is needed at runtime).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import countries  # noqa: E402

MARGIN, LABEL_MARGIN, LABEL_CLEARANCE = 0.75, 0.2, 0.035
UNLABELLED = {"Disputed", "Indeterminate"}


def _round(value, digits=4):
    if isinstance(value, (list, tuple)):
        return [_round(v, digits) for v in value]
    return round(value, digits)


def build(features: list[dict], iso3: str) -> dict | None:
    from shapely.geometry import box, mapping, shape
    from shapely.validation import make_valid

    shapes = [(f["properties"], make_valid(shape(f["geometry"]))) for f in features if f.get("geometry")]
    own = [geom for props, geom in shapes if props.get("ADM0_A3") == iso3]
    if not own:
        return None
    from shapely.ops import unary_union

    country = unary_union(own)
    xmin, ymin, xmax, ymax = country.bounds
    span = max(xmax - xmin, ymax - ymin)
    pad = span * MARGIN
    bounds = _round([xmin - pad, ymin - pad, xmax + pad, ymax + pad])
    clip = box(*bounds)
    near = box(xmin - span * LABEL_MARGIN, ymin - span * LABEL_MARGIN, xmax + span * LABEL_MARGIN, ymax + span * LABEL_MARGIN)
    inner = box(xmin, ymin, xmax, ymax)
    clearance = country.buffer(span * LABEL_CLEARANCE)
    out = []
    for props, geom in shapes:
        if not geom.intersects(clip):
            continue
        code = str(props.get("ADM0_A3"))
        clipped = geom.intersection(clip).simplify(span / 1500, preserve_topology=True)
        if clipped.is_empty or clipped.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        labels = []
        if code != iso3 and str(props.get("TYPE")) not in UNLABELLED:
            zone = geom.intersection(near).difference(clearance)
            ring = zone.intersection(inner)
            if not ring.is_empty and ring.area > 0.004 * near.area:
                labels.append(_round(list(ring.representative_point().coords[0]), 3))
            if not zone.is_empty and zone.area > 0.01 * near.area:
                labels.append(_round(list(zone.representative_point().coords[0]), 3))
        geometry = mapping(clipped)
        out.append({"type": "Feature", "properties": {"iso3": code, "name": str(props.get("NAME")), "self": code == iso3, "labels": labels},
                    "geometry": {"type": geometry["type"], "coordinates": _round(geometry["coordinates"])}})
    return {"type": "FeatureCollection", "bbox": bounds, "features": out}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("natural_earth", type=Path)
    parser.add_argument("--only", help="ISO3 code to (re)build")
    args = parser.parse_args()
    features = json.loads(args.natural_earth.read_text(encoding="utf-8"))["features"]
    target = ROOT / "assets" / "geo" / "context"
    target.mkdir(parents=True, exist_ok=True)
    for country in countries.REGISTRY:
        path = target / f"{country.slug}.json"
        if args.only and country.iso3 != args.only.upper():
            continue
        if path.exists() and not args.only:
            continue
        result = build(features, country.iso3)
        if result is None:
            print(f"{country.iso3}: not in Natural Earth, skipped")
            continue
        path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
        print(f"{country.iso3}: {len(result['features'])} features -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
