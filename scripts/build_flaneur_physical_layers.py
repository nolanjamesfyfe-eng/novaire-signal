#!/usr/bin/env python3
"""Build compact Flâneur physical layers from Natural Earth public-domain data."""
from __future__ import annotations
import io, json, math, os, tempfile, urllib.request, zipfile
from pathlib import Path

import shapefile
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "map"
CACHE = Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "flaneur-physical-layers"
SOURCES = {
    "marine": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_geography_marine_polys.zip",
    "lakes": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip",
    "regions": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_geography_regions_polys.zip",
    "relief": "https://naturalearth.s3.amazonaws.com/50m_raster/GRAY_50M_SR_W.zip",
}


def fetch_zip(key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{key}.zip"
    if not target.exists():
        with urllib.request.urlopen(SOURCES[key], timeout=120) as response:
            target.write_bytes(response.read())
    folder = CACHE / key
    if not folder.exists():
        folder.mkdir()
        with zipfile.ZipFile(target) as archive:
            archive.extractall(folder)
    return folder


def reader(folder: Path) -> shapefile.Reader:
    return shapefile.Reader(str(next(folder.glob("*.shp"))))


def fields(r: shapefile.Reader) -> list[str]:
    return [field[0] for field in r.fields[1:]]


def shape_anchor(shape: shapefile.Shape) -> list[float]:
    # Natural Earth polygons are label envelopes; bbox midpoint is stable and remains source-backed.
    x0, y0, x1, y1 = shape.bbox
    return [round((x0 + x1) / 2, 4), round((y0 + y1) / 2, 4)]


def build_labels() -> dict:
    layers = []
    for key, kind in (("marine", "water"), ("lakes", "lake"), ("regions", "terrain")):
        r = reader(fetch_zip(key)); names = fields(r)
        for shape_record in r.iterShapeRecords():
            row = dict(zip(names, shape_record.record))
            row = {str(k).lower(): v for k, v in row.items()}
            feature = str(row.get("featurecla", ""))
            if kind == "terrain" and feature != "Range/mtn":
                continue
            if kind == "lake":
                name = str(row.get("label") or row.get("name") or row.get("name_en") or "").strip()
            else:
                name = str(row.get("name_en") or row.get("name") or row.get("label") or "").strip()
            if not name:
                continue
            rank = int(row.get("scalerank", 9) or 9)
            important = {"Black Sea", "Caspian Sea", "Lake Baikal", "Lake Victoria", "Lake Superior", "Lake Michigan", "Lake Huron", "Lake Erie", "Lake Ontario", "Rocky Mountains", "Caucasus Mountains", "Andes"}
            if name in important:
                rank = -2
            source_min = float(row.get("min_label", row.get("min_zoom", 4)) or 4)
            if kind == "water":
                minimum = 1 if rank == 0 else max(1.3, min(5.8, 1.15 + rank * .48))
            elif kind == "lake":
                minimum = max(2.0, min(8.0, 1.6 + rank * .67))
            else:
                minimum = max(1.8, min(6.5, source_min * .82))
            layers.append({"n": name.title() if name.isupper() else name, "c": shape_anchor(shape_record.shape), "k": kind, "r": rank, "z": round(minimum, 2)})
    layers.sort(key=lambda item: (item["k"], item["r"], item["n"]))
    counts = {kind: sum(item["k"] == kind for item in layers) for kind in ("water", "lake", "terrain")}
    return {"source": "Natural Earth 1:10m physical vectors v5.x", "license": "Public domain", "counts": counts, "labels": layers}


def build_relief() -> None:
    folder = fetch_zip("relief")
    image = Image.open(next(folder.glob("*.tif"))).convert("L")
    image.thumbnail((1440, 720), Image.Resampling.LANCZOS)
    # Gray Earth encodes ocean and lake water as a flat 106 gray. Make that
    # neutral for multiply blending so the projected texture is land-only.
    image = image.point([255 if 103 <= value <= 109 else value for value in range(256)])
    image = ImageEnhance.Contrast(image).enhance(1.35).filter(ImageFilter.GaussianBlur(.25))
    image.save(OUT / "natural-earth-relief.webp", "WEBP", quality=72, method=6)


def main() -> None:
    labels = build_labels()
    (OUT / "physical-labels.json").write_text(json.dumps(labels, ensure_ascii=False, separators=(",", ":")) + "\n")
    build_relief()
    print(json.dumps({"counts": labels["counts"], "labels_bytes": (OUT / "physical-labels.json").stat().st_size, "relief_bytes": (OUT / "natural-earth-relief.webp").stat().st_size}))


if __name__ == "__main__":
    main()
