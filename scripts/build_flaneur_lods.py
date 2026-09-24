#!/usr/bin/env python3
"""Build topology-clean globe LODs from the canonical world geometry."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "map/world.geojson"
LEVELS = {
    "world-globe.geojson": ("0.5%", "0.001"),
    "world-globe-medium.geojson": ("1%", "0.001"),
    # High zoom is viewport-culled before drawing, so spend the saved frame
    # budget on coastline fidelity instead of reusing the overview geometry.
    "world-globe-detail.geojson": ("4.5%", "0.001"),
    # Loaded only after 3x zoom. Natural Earth 1:10m detail keeps Hawaiian
    # coastlines and compact jurisdictions useful without a token-gated tile API.
    "world-globe-high.geojson": ("20%", "0.0001"),
}


def reverse_rings(geometry: dict) -> None:
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        for ring in polygon:
            ring.reverse()  # D3 spherical exterior winding; mapshaper writes RFC 7946 winding.


def point_count(value) -> int:
    if isinstance(value, list):
        return 1 if value and isinstance(value[0], (int, float)) else sum(point_count(v) for v in value)
    if isinstance(value, dict):
        return sum(point_count(v) for v in value.values())
    return 0


def main() -> None:
    for filename, (percentage, precision) in LEVELS.items():
        target = ROOT / "map" / filename
        temporary = target.with_suffix(".tmp.geojson")
        subprocess.run([
            "npx", "--yes", "mapshaper", str(SOURCE), "-clean", "-simplify", percentage,
            "keep-shapes", "weighted", "-o", "format=geojson", f"precision={precision}", str(temporary),
        ], check=True)
        data = json.loads(temporary.read_text())
        if len(data.get("features", [])) != 199:
            raise RuntimeError(f"{filename}: expected 199 features")
        for feature in data["features"]:
            reverse_rings(feature["geometry"])
        target.write_text(json.dumps(data, separators=(",", ":")) + "\n")
        temporary.unlink()
        print(f"{filename}: {point_count(data):,} points, {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
