#!/usr/bin/env python3
"""Build compact Flâneur physical layers from Natural Earth public-domain data."""
from __future__ import annotations
import hashlib, io, json, math, os, shutil, subprocess, tempfile, urllib.request, zipfile
from pathlib import Path

import shapefile
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "map"
CACHE = Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "flaneur-physical-layers"
SOURCES = {
    "marine": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_geography_marine_polys.zip",
    "lakes": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip",
    "regions": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_geography_regions_polys.zip",
    "relief": "https://naturalearth.s3.amazonaws.com/10m_raster/HYP_HR_SR_OB_DR.zip",
    "admin1": "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip",
}
SOURCE_SHA256 = {"relief": "ee2cbbf5b682e8514374c0c318bbf49aa640ecfe60d0a2e09a90e0c575d30a78"}

# Deliberately small: five oceans and only globally prominent, large seas. Bays,
# gulfs, straits, channels, marginal local seas, and all lakes are excluded.
MAJOR_WATER = {
    "Atlantic Ocean": [-31, 5], "Pacific Ocean": [-150, 2], "Indian Ocean": [78, -20],
    "Arctic Ocean": [0, 78], "Southern Ocean": [95, -58], "Black Sea": None,
    "Mediterranean Sea": None, "Caribbean Sea": None, "Red Sea": None,
    "Arabian Sea": None, "South China Sea": None, "Bering Sea": [-175, 58.5],
    "Coral Sea": None, "Philippine Sea": None, "Tasman Sea": None,
    "Sea of Japan": None, "Baltic Sea": None, "North Sea": None,
}


def fetch_zip(key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{key}.zip"
    if target.exists() and key in SOURCE_SHA256 and hashlib.sha256(target.read_bytes()).hexdigest() != SOURCE_SHA256[key]:
        target.unlink()
        shutil.rmtree(CACHE / key, ignore_errors=True)
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
    for key, kind in (("marine", "water"), ("regions", "terrain")):
        r = reader(fetch_zip(key)); names = fields(r)
        for shape_record in r.iterShapeRecords():
            row = dict(zip(names, shape_record.record))
            row = {str(k).lower(): v for k, v in row.items()}
            feature = str(row.get("featurecla", ""))
            if kind == "terrain" and feature != "Range/mtn":
                continue
            name = str(row.get("name_en") or row.get("name") or row.get("label") or "").strip()
            if not name:
                continue
            if kind == "water" and name not in MAJOR_WATER:
                continue
            rank = int(row.get("scalerank", 9) or 9)
            important = {"Black Sea", "Rocky Mountains", "Caucasus Mountains", "Andes"}
            if name in important:
                rank = -2
            source_min = float(row.get("min_label", row.get("min_zoom", 4)) or 4)
            if kind == "water":
                minimum = 1 if "Ocean" in name else max(1.5, min(3.0, 1.35 + rank * .35))
            else:
                minimum = max(1.8, min(6.5, source_min * .82))
            anchor = MAJOR_WATER.get(name) if kind == "water" else None
            layers.append({"n": name.title() if name.isupper() else name, "c": anchor or shape_anchor(shape_record.shape), "k": kind, "r": rank, "z": round(minimum, 2)})
    # The Natural Earth Pacific and Atlantic are split at the antimeridian/equator.
    # Canonicalize every approved water name to one label and one stable anchor.
    water = {}
    for item in layers:
        if item["k"] == "water":
            water.setdefault(item["n"], item)
    layers = [item for item in layers if item["k"] != "water"] + list(water.values())
    layers.sort(key=lambda item: (item["k"], item["r"], item["n"]))
    counts = {kind: sum(item["k"] == kind for item in layers) for kind in ("water", "lake", "terrain")}
    return {"source": "Natural Earth 1:10m physical vectors v5.x", "license": "Public domain", "counts": counts, "labels": layers}


def build_admin1() -> dict:
    r = reader(fetch_zip("admin1")); names = fields(r); features = []
    expected = {"US": 51, "CA": 13}
    for shape_record in r.iterShapeRecords():
        row = dict(zip(names, shape_record.record)); country = row.get("iso_a2")
        if country not in expected:
            continue
        subdivision_name = row.get("name") or row.get("name_en")
        if country == "US" and row.get("postal") == "DC":
            subdivision_name = "District of Columbia"
        features.append({"type": "Feature", "properties": {
            "country": country, "code": row.get("postal"), "name": subdivision_name,
            "label": [round(float(row["longitude"]), 4), round(float(row["latitude"]), 4)],
        }, "geometry": shape_record.shape.__geo_interface__})
    counts = {country: sum(f["properties"]["country"] == country for f in features) for country in expected}
    if counts != expected:
        raise RuntimeError(f"admin-1 coverage mismatch: {counts}")
    raw = OUT / "north-america-admin1.raw.geojson"; target = OUT / "north-america-admin1.geojson"
    raw.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    subprocess.run(["npx", "--yes", "mapshaper", str(raw), "-clean", "-simplify", "5%", "keep-shapes", "weighted", "-o", "format=geojson", "precision=0.001", str(target)], check=True)
    raw.unlink()
    data = json.loads(target.read_text())
    # mapshaper preserves source properties; compact serialization is smaller than its default output.
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"counts": counts, "bytes": target.stat().st_size}


def build_relief() -> None:
    folder = fetch_zip("relief")
    Image.MAX_IMAGE_PIXELS = None
    image = Image.open(next(folder.glob("*.tif"))).convert("RGB")
    image.thumbnail((4320, 2160), Image.Resampling.LANCZOS)
    r, g, b = image.split()
    # Natural Earth ocean bathymetry is blue. Preserve it as geographically
    # derived texture while keeping a hard land/water channel for compositing.
    blue_over_red = ImageChops.subtract(b, r).point(lambda value: 255 if value > 12 else 0)
    blue_over_green = ImageChops.subtract(b, g).point(lambda value: 255 if value > 4 else 0)
    ocean_mask = ImageChops.multiply(blue_over_red, blue_over_green).filter(ImageFilter.GaussianBlur(.45))
    shade = ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(2.15)
    ochre = ImageOps.colorize(shade, "#171711", "#edcc89")
    # Keep genuine Natural Earth hypsometric variation—olive lowlands, arid
    # ochres, and bright/dark ridge faces—rather than inventing mountain forms.
    land = Image.blend(ImageEnhance.Color(image).enhance(.68), ochre, .69)
    water = ImageOps.colorize(ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(1.45), "#08272e", "#537f82")
    vintage = Image.composite(water, land, ocean_mask).convert("RGBA")
    # Alpha is metadata for the renderer: 96 water, 255 land.
    vintage.putalpha(Image.composite(Image.new("L", image.size, 96), Image.new("L", image.size, 255), ocean_mask))
    vintage.save(OUT / "natural-earth-relief.webp", "WEBP", quality=82, method=6)


def main() -> None:
    labels = build_labels()
    (OUT / "physical-labels.json").write_text(json.dumps(labels, ensure_ascii=False, separators=(",", ":")) + "\n")
    admin1 = build_admin1()
    build_relief()
    (OUT / "terrain-source.json").write_text(json.dumps({
        "source": "Natural Earth I 1:10m HYP_HR_SR_OB_DR", "url": SOURCES["relief"],
        "sourceSha256": SOURCE_SHA256["relief"], "license": "Public domain",
        "derivativeResolution": [4320, 2160],
        "treatment": "Vintage recolor of cross-blended hypsometric tint, shaded relief, ocean bottom, and drainage",
    }, separators=(",", ":")) + "\n")
    print(json.dumps({"counts": labels["counts"], "labels_bytes": (OUT / "physical-labels.json").stat().st_size, "admin1": admin1, "relief_bytes": (OUT / "natural-earth-relief.webp").stat().st_size}))


if __name__ == "__main__":
    main()
