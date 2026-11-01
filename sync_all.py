"""
sync_all.py — keeps the Iltatähti P-18 3D model, the laser SVGs and the building
drawing in sync. Run it after any change (or keep it running with --watch).

It compares the files with the state of the previous sync (.sync_state.json,
SHA-256 of every source and of every laser SVG it wrote) and decides:

  3D model changed   (p18_iltatahti.py, dxf_parts.py, the DXF, pukki.py,
                      pukki.txt, overrides/*.json)
                     -> 3D model (OCP, STEP, GLB) + laser SVGs + building drawing
  laser SVG edited   (laser/osat*.svg changed after it was written, e.g. in
                      Inkscape: a part outline moved, notch widened ...)
                     -> the edited outlines are read back into the model as
                        overrides/<part>.json, then 3D model + new laser SVGs +
                        building drawing; the edited SVG is moved to laser/arkisto
  to_laser.py changed  -> laser SVGs
  drawing.py changed   -> building drawing
  nothing changed      -> nothing to do

Laser edits are mapped back with the placement matrix that to_laser.py writes into
every part group (data-matrix): the cut lines of the part (tab gaps closed) are
turned back into the part's own coordinates. Spare parts "(vara)" are ignored.

Run:  .venv/bin/python sync_all.py            sync once
      .venv/bin/python sync_all.py --watch    sync on every save
      .venv/bin/python sync_all.py --force    rebuild everything
      .venv/bin/python sync_all.py --no-viewer
"""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
STATE = HERE / ".sync_state.json"
LASER_DIR = HERE / "laser"
ARCHIVE = LASER_DIR / "arkisto"
OVERRIDE_DIR = HERE / "overrides"

MODEL_SRC = ["p18_iltatahti.py", "dxf_parts.py", "hyttynen4-indoor-ff-supply-5cm-49cm.dxf", "pukki.py", "pukki.txt"]
LASER_SRC = ["to_laser.py"]
DRAWING_SRC = ["drawing.py"]
SHAPE_TOL = 0.05  # mm: smaller differences between an edited outline and the model are noise


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> dict[str, list[Path]]:
    return {
        "model": [HERE / f for f in MODEL_SRC] + sorted(OVERRIDE_DIR.glob("*.json")),
        "laser": [HERE / f for f in LASER_SRC],
        "drawing": [HERE / f for f in DRAWING_SRC],
    }


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"src": {}, "laser": {}}


def save_state(laser_files):
    state = {"src": {str(f.relative_to(HERE)): sha(f) for fs in sources().values() for f in fs if f.exists()},
             "laser": {f.name: sha(f) for f in laser_files if f.exists()},
             "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    STATE.write_text(json.dumps(state, indent=1))


def changed_sources(state) -> dict[str, list[str]]:
    out = {}
    known = state.get("src", {})
    for group, files in sources().items():
        ch = [str(f.relative_to(HERE)) for f in files if f.exists() and known.get(str(f.relative_to(HERE))) != sha(f)]
        # a deleted override is a model change too
        if group == "model":
            ch += [k for k in known if k.startswith("overrides/") and not (HERE / k).exists()]
        if ch:
            out[group] = ch
    return out


def edited_laser_files(state) -> list[Path]:
    known = state.get("laser", {})
    return [f for f in sorted(LASER_DIR.glob("osat*.svg")) if f.name in known and known[f.name] != sha(f)]


def current_laser_files(state) -> list[Path]:
    return [LASER_DIR / n for n in state.get("laser", {}) if (LASER_DIR / n).exists()]


# --------------------------------------------------------------------------
# reading part outlines back from an edited laser SVG
# --------------------------------------------------------------------------
def _parts_in_svg(path: Path):
    """Yield (part name, matrix, sheet_w, [polylines in the part's sheet frame]) per part group.

    Transforms on the part group or the layers above it are ignored: they come from
    moving a whole part on the sheet, which does not change its shape. Node edits
    (the path data, and a transform on a single path) are read.
    """
    from svgelements import Matrix, Path as SvgPath

    for g in ET.parse(path).getroot().iter():
        if g.tag.split("}")[-1] != "g" or "data-matrix" not in g.attrib:
            continue
        lines = []
        for p in g.iter():
            if p.tag.split("}")[-1] != "path" or "d" not in p.attrib:
                continue
            sp = SvgPath(p.attrib["d"])
            if "transform" in p.attrib:
                sp = sp * Matrix(p.attrib["transform"])
            for sub in sp.as_subpaths():
                pts = []
                for seg in sub:
                    kind = type(seg).__name__
                    n = 1 if kind in ("Line", "Close", "Move") else 12
                    for k in range(1, n + 1):
                        q = seg.point(k / n)
                        if q is not None and (not pts or math.dist(pts[-1], (q.x, q.y)) > 1e-6):
                            pts.append((q.x, q.y))
                if len(pts) > 1:
                    lines.append(pts)
        yield (g.attrib.get("data-name", ""), [float(v) for v in g.attrib["data-matrix"].split()],
               float(g.attrib.get("data-sheet-w", "50")), lines)


def _rings(lines, gap=3.0):
    """Close the tab gaps: chain the cut pieces into rings. Closed pieces are holes."""
    closed = [l for l in lines if math.dist(l[0], l[-1]) < 1e-3]
    open_ = [l for l in lines if math.dist(l[0], l[-1]) >= 1e-3]
    rings = []
    while open_:
        ring = open_.pop(max(range(len(open_)), key=lambda i: len(open_[i])))
        while open_:
            end = ring[-1]
            k, rev, d = min(((i, r, math.dist(end, l[-1] if r else l[0])) for i, l in enumerate(open_) for r in (0, 1)),
                            key=lambda t: t[2])
            if d > gap:
                break
            nxt = open_.pop(k)
            ring += nxt[::-1] if rev else nxt
        rings.append(ring)
    return rings, closed


def import_laser_file(path: Path, model_raws: dict) -> list[str]:
    """Write overrides for the parts whose outline differs from the model; returns their names."""
    from shapely import affinity
    from shapely.geometry import Polygon

    OVERRIDE_DIR.mkdir(exist_ok=True)
    changed = []
    for name, (a, b, c, d, e, f), sheet_w, lines in _parts_in_svg(path):
        if not name or "(vara)" in name or name not in model_raws:
            continue
        rings, holes = _rings(lines)
        if not rings:
            continue
        outer = max(rings, key=lambda r: Polygon(r).area if len(r) > 2 else 0)
        # SVG (y down) -> sheet (y up) -> the part's own coordinates (inverse placement)
        det = a * d - b * c
        inv = [d / det, -b / det, -c / det, a / det, (b * f - d * e) / det, (c * e - a * f) / det]

        def back(pts):
            poly = Polygon([(x, sheet_w - y) for x, y in pts])
            return affinity.affine_transform(poly, inv)
        new = back(outer)
        hs = [back(h) for h in holes]
        if hs:
            new = Polygon(new.exterior.coords, [h.exterior.coords for h in hs])
        new = new.buffer(0)
        if new.geom_type != "Polygon":
            new = max(new.geoms, key=lambda g: g.area)
        old = model_raws[name]
        if new.hausdorff_distance(old) <= SHAPE_TOL:
            continue
        data = {"part": name, "from": path.name, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "outer": [[round(x, 4), round(y, 4)] for x, y in list(new.exterior.coords)[:-1]],
                "holes": [[[round(x, 4), round(y, 4)] for x, y in list(i.coords)[:-1]] for i in new.interiors]}
        (OVERRIDE_DIR / f"{name}.json").write_text(json.dumps(data, indent=1))
        changed.append(f"{name} (ero {new.hausdorff_distance(old):.2f} mm)")
    return changed


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------
def archive_laser(keep: list[Path]):
    """Move every laser SVG that is not part of the current set to laser/arkisto."""
    keep_names = {f.name for f in keep}
    for f in LASER_DIR.glob("osat*.svg"):
        if f.name not in keep_names:
            ARCHIVE.mkdir(exist_ok=True)
            shutil.move(str(f), str(ARCHIVE / f.name))


def sync(force=False, viewer=True) -> bool:
    state = load_state()
    first = not state.get("src")
    changed = changed_sources(state)
    edited = edited_laser_files(state)

    imported = []
    if edited:
        import p18_iltatahti as model
        import to_laser

        _, flat, _ = model.build()
        raws = {p.name: to_laser.profile_raw(p) for p in flat}
        for f in edited:
            ch = import_laser_file(f, raws)
            print(f"Laser-SVG muokattu: {f.name} -> " + (", ".join(ch) if ch else "ei muotomuutoksia"))
            imported += ch
            ARCHIVE.mkdir(exist_ok=True)
            shutil.move(str(f), str(ARCHIVE / f.name.replace(".svg", ".muokattu.svg")))

    model_changed = force or first or "model" in changed or bool(imported) or bool(edited)
    outputs = []
    if model_changed:
        outputs = ["3d", "laser", "drawing"]
    else:
        if "laser" in changed:
            outputs.append("laser")
        if "drawing" in changed:
            outputs.append("drawing")

    for group, files in changed.items():
        print(f"Muuttunut ({group}): {', '.join(files)}")
    if not outputs:
        print("Kaikki ajan tasalla: 3D-malli, laser-SVG:t ja rakennuspiirustus vastaavat lähteitä.")
        return False

    print(f"Päivitetään: {', '.join({'3d': '3D-malli', 'laser': 'laser-SVG:t', 'drawing': 'rakennuspiirustus'}[o] for o in outputs)}")
    import p18_iltatahti as model

    result = model.update_all(viewer=viewer, outputs=tuple(outputs))
    laser_now = result["laser"] or current_laser_files(state)
    if result["laser"]:
        archive_laser(result["laser"])
    save_state(laser_now)
    print(f"\nSynkronoitu {time.strftime('%H:%M:%S')}.")
    return True


def watch(viewer=True, interval=1.0):
    """Sync on every change; each sync runs in a fresh process so script edits apply."""
    cmd = [sys.executable, str(Path(__file__).resolve())] + ([] if viewer else ["--no-viewer"])

    def stamp():
        files = [f for fs in sources().values() for f in fs] + list(LASER_DIR.glob("osat*.svg"))
        return {f: f.stat().st_mtime for f in files if f.exists()}

    subprocess.run(cmd)
    last = stamp()
    print(f"\n[{time.strftime('%H:%M:%S')}] seurataan muutoksia (Ctrl+C lopettaa)")
    try:
        while True:
            time.sleep(interval)
            now = stamp()
            if now != last:
                time.sleep(0.5)  # let the editor finish writing
                subprocess.run(cmd)
                last = stamp()
                print(f"[{time.strftime('%H:%M:%S')}] seurataan muutoksia")
    except KeyboardInterrupt:
        print("\nSeuranta lopetettu.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Iltatähti P-18: 3D-malli, laser-SVG:t ja rakennuspiirustus synkronissa")
    ap.add_argument("--watch", action="store_true", help="synkronoi aina kun jokin tiedosto muuttuu")
    ap.add_argument("--force", action="store_true", help="päivitä kaikki muutoksista riippumatta")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE))
    if args.watch:
        watch(viewer=not args.no_viewer)
    else:
        sync(force=args.force, viewer=not args.no_viewer)
