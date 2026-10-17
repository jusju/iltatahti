"""
Laser export for p18_iltatahti.py: nests every flat balsa part of the 3D model
onto ~50 x 500 mm balsa sheets and writes one SVG per sheet.

  - grain: every part is turned so that its grain (FlatPart.grain) runs along
    the long side of the sheet; only grain-preserving flips are used in nesting
  - nesting: bottom-left fill on the true part outlines, largest parts first
  - cut lines: red Inkscape hairline (1 px, non-scaling stroke, -inkscape-stroke:hairline)
  - part numbers: engraved, black fill, no stroke; not on wing ribs or on parts
    too narrow for DIGIT_MIN_H digits
  - tabs: TAB_W mm uncut bridges in every outline so parts stay in the sheet
  - 4 mm: a single sheet, free space filled with spare motor sticks
  - osat_esitys.svg: every part with its number, name and size, for discussing changes

Files (in laser/):  osat2mm-1-<time>.svg, osat2mm-2-<time>.svg, ..., osat4mm-<time>.svg
with <time> = vvvv-kk-pp-tt-mm-ss.

Run:  .venv/bin/python to_laser.py
"""

from datetime import datetime
from math import atan2, degrees
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring, unary_union
from shapely.prepared import prep

import p18_iltatahti as model

SHEET_W = 50.0  # across the grain
SHEET_L = 500.0  # along the grain
EDGE = 1.0  # keep away from the sheet edges
# per sheet thickness: wider margin all round (easier to align the sheet in the laser),
# and the part groups spread evenly along the whole strip instead of packed to the left
MARGIN = {model.SHEET_T: 3.0}
GAP = 1.0  # between parts
TAB_W = 1.0  # uncut bridge length
TAB_SPACING = 60.0  # one tab per this much outline, at least 2 per part
CORNER_ANGLE = 35.0  # no tabs within 0.5 mm of a corner sharper than this
DIGIT_MAX_H, DIGIT_MIN_H = 4.0, 2.5  # smaller would not be readable
LABEL_MARGIN = 0.3  # engraving distance from the part outline
FLATTEN_TOL = 0.02  # curve to polyline tolerance
# single sheet thicknesses: after the model's parts, add spares in this order;
# (part name, how many, None = as many as fit)
FILLER = {model.STICK_W: [("motor_stick", 2), ("wing_wedge", None)]}
OUT_DIR = Path(__file__).parent / "laser"
TAB_COUNT: list[int] = []  # tabs per written part, for the check in main()
MARKS: dict = {}  # part name -> engraved marks (shapely polygons in the part's own coordinates)
OVERVIEW = Path(__file__).parent / "osat_esitys.svg"


def engrave_number(name: str) -> bool:
    """Wing ribs get a number only where a full-size one fits (the wide full ribs)."""
    return not (name.startswith("wing_") and "_rib" in name)


def label_for_part(name: str, poly: Polygon, text: str):
    if engrave_number(name):
        return label_for(poly, text)
    lab = label_for(poly, text)
    return lab if lab is not None and lab.bounds[3] - lab.bounds[1] > DIGIT_MAX_H - 0.05 else None

# Inkscape hairline: always 1 screen pixel wide, whatever the zoom or document units
HAIRLINE = "stroke-width:1px;vector-effect:non-scaling-stroke;-inkscape-stroke:hairline"
CUT_STYLE = f"fill:none;stroke:#ff0000;{HAIRLINE}"
ENGRAVE_STYLE = "fill:#000000;fill-rule:evenodd;stroke:none"


# --------------------------------------------------------------------------
# Profile -> polygon
# --------------------------------------------------------------------------
def wire_coords(wire) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for e in wire.order_edges():
        if e.geom_type.name == "LINE":
            seg = [e.position_at(0), e.position_at(1)]
        else:
            n = max(8, int(e.length / 0.5))
            seg = [e.position_at(i / n) for i in range(n + 1)]
        seg = [(p.X, p.Y) for p in seg]
        if pts:
            d0 = (seg[0][0] - pts[-1][0]) ** 2 + (seg[0][1] - pts[-1][1]) ** 2
            d1 = (seg[-1][0] - pts[-1][0]) ** 2 + (seg[-1][1] - pts[-1][1]) ** 2
            if d1 < d0:
                seg.reverse()
            seg = seg[1:]
        pts += seg
    return pts


def profile_raw(part: model.FlatPart) -> Polygon:
    """The part's profile as a polygon in its own (model) coordinates."""
    face = part.profile
    poly = Polygon(wire_coords(face.outer_wire()), [wire_coords(w) for w in face.inner_wires()])
    return poly.simplify(FLATTEN_TOL / 2)


def profile_polygon(part: model.FlatPart) -> Polygon:
    poly = affinity.rotate(profile_raw(part), -part.grain, origin=(0, 0))  # grain -> sheet X
    return normalize(poly)


def placement_matrix(raw: Polygon, placed: Polygon) -> tuple:
    """Affine (a, b, c, d, e, f) with X = a x + b y + e, Y = c x + d y + f taking the
    part's own coordinates to the sheet (y up). The placed polygon comes from the raw
    one by rotations, flips and translations only, so the vertices correspond."""
    import numpy as np

    src = np.array(raw.exterior.coords)
    dst = np.array(placed.exterior.coords)
    A = np.hstack([src, np.ones((len(src), 1))])
    sol, *_ = np.linalg.lstsq(A, dst, rcond=None)  # 3x2
    (a, c), (b, d), (e, f) = sol
    return tuple(float(v) for v in (a, b, c, d, e, f))


def normalize(poly: Polygon) -> Polygon:
    x0, y0, _, _ = poly.bounds
    return affinity.translate(poly, -x0, -y0)


def orientations(poly: Polygon) -> list[Polygon]:
    """Flips that keep the grain along X."""
    out = []
    for xf, yf in ((1, 1), (-1, -1), (-1, 1), (1, -1)):
        p = normalize(affinity.scale(poly, xf, yf, origin=(0, 0)))
        if not any(p.equals_exact(q, 1e-6) for q in out):
            out.append(p)
    return out


# --------------------------------------------------------------------------
# Nesting: bottom-left fill
# --------------------------------------------------------------------------
class Sheet:
    def __init__(self, edge=EDGE, gap=GAP, x_step=None):
        self.edge, self.gap = edge, gap
        self.x_step = x_step  # also try x positions on this grid (fills holes between odd shapes)
        self.placed: list[tuple[int, str, Polygon]] = []
        self.blocked = None  # union of placed parts grown by the gap

    def collides(self, poly: Polygon) -> bool:
        x0, y0, x1, y1 = poly.bounds
        ex = 0.0 if full_length(poly) else self.edge  # a full-length strip uses the sheet ends as its ends
        if x0 < ex - 1e-9 or y0 < self.edge - 1e-9 or x1 > SHEET_L - ex + 1e-9 or y1 > SHEET_W - self.edge + 1e-9:
            return True
        return self.blocked is not None and self.blocked.intersects(poly)

    def add(self, num: int, name: str, poly: Polygon):
        self.placed.append((num, name, poly))
        self.blocked = prep(unary_union([p for _, _, p in self.placed]).buffer(self.gap, join_style="mitre"))

    def find_spot(self, poly: Polygon):
        """Lowest-leftmost position for poly (already at origin). Returns (score, placed poly)."""
        w = poly.bounds[2]
        xs = {0.0 if full_length(poly) else self.edge}
        for _, _, p in self.placed:
            b = p.bounds
            xs |= {b[0], b[2] + self.gap + 0.05}  # just clear of the gap, touching counts as a collision
        if self.x_step and self.placed:
            right = max(p.bounds[2] for _, _, p in self.placed)
            xs |= {self.edge + k * self.x_step for k in range(int((right - self.edge) / self.x_step) + 1)}
        best = None
        for x in sorted(xs):
            if x + w > SHEET_L - (0.0 if full_length(poly) else self.edge) + 1e-9:
                continue
            y = self._lowest_y(poly, x)
            if y is None:
                continue
            x = self._slide_left(poly, x, y)
            cand = affinity.translate(poly, x, y)
            score = (cand.bounds[2], y)  # keep the used sheet length short
            if best is None or score < best[0]:
                best = (score, cand)
        return best

    def _lowest_y(self, poly, x):
        h = poly.bounds[3]
        y, top = self.edge, SHEET_W - self.edge - h
        while y <= top + 1e-9:
            if not self.collides(affinity.translate(poly, x, y)):
                lo = y - 1.0
                while y - 0.1 >= max(lo, self.edge) - 1e-9 and not self.collides(affinity.translate(poly, x, y - 0.1)):
                    y -= 0.1
                return y
            y += 1.0
        return None

    def _slide_left(self, poly, x, y):
        while x - 0.25 >= (0.0 if full_length(poly) else self.edge) and not self.collides(affinity.translate(poly, x - 0.25, y)):
            x -= 0.25
        return x


def nest(items, single_sheet=False, edge=EDGE, gap=GAP, x_step=None):
    """items: [(num, name, polygon)] -> list of Sheet."""
    sheets: list[Sheet] = []
    items = sorted(items, key=lambda it: (-it[2].bounds[2], -it[2].area))
    for num, name, poly in items:
        b = poly.bounds
        if b[2] > SHEET_L + 1e-6 or b[3] > SHEET_W - 2 * edge:
            raise ValueError(f"{num} {name} ({b[2]:.0f} x {b[3]:.0f} mm) does not fit a "
                             f"{SHEET_W:.0f} x {SHEET_L:.0f} mm sheet")
        for sheet in sheets:
            spots = [s for s in (sheet.find_spot(o) for o in orientations(poly)) if s]
            if spots:
                sheet.add(num, name, min(spots, key=lambda s: s[0])[1])
                break
        else:
            if single_sheet and sheets:
                raise ValueError(f"{name} does not fit on the single sheet")
            sheets.append(Sheet(edge, gap, x_step))
            spot = min((s for s in (sheets[-1].find_spot(o) for o in orientations(poly)) if s),
                       key=lambda s: s[0])
            sheets[-1].add(num, name, spot[1])
    return sheets


def spread(sheet: Sheet):
    """Move the part groups apart along the strip, evenly over its whole usable length.
    A group = parts whose X ranges overlap (they interlock across the strip); every
    group moves as one piece and the gaps between groups only grow, so nothing collides."""
    items = sorted(sheet.placed, key=lambda it: it[2].bounds[0])
    groups = []
    for it in items:
        if groups and it[2].bounds[0] < groups[-1][1] + sheet.gap:
            groups[-1][0].append(it)
            groups[-1][1] = max(groups[-1][1], it[2].bounds[2])
        else:
            groups.append([[it], it[2].bounds[2]])
    widths = [g[1] - min(p.bounds[0] for _, _, p in g[0]) for g in groups]
    free = SHEET_L - 2 * sheet.edge - sum(widths)
    if len(groups) < 2 or free <= 0:
        return
    gap = free / (len(groups) - 1)
    sheet.placed, x = [], sheet.edge
    for (members, _), w in zip(groups, widths):
        dx = x - min(p.bounds[0] for _, _, p in members)
        sheet.placed += [(n, name, affinity.translate(p, dx, 0)) for n, name, p in members]
        x += w + gap
    sheet.add(*sheet.placed.pop())  # rebuild the collision area


def fill_spares(sheet: Sheet, num: int, name: str, poly: Polygon, limit=None) -> int:
    count = 0
    while limit is None or count < limit:
        spots = [s for s in (sheet.find_spot(o) for o in orientations(poly)) if s]
        if not spots:
            return count
        sheet.add(num, f"{name} (vara)", min(spots, key=lambda s: s[0])[1])
        count += 1
    return count


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
def corner_positions(ring: LineString) -> list[float]:
    c = list(ring.coords)[:-1]
    out, s = [], 0.0
    for i in range(len(c)):
        a, b, d = c[i - 1], c[i], c[(i + 1) % len(c)]
        turn = degrees(atan2(d[1] - b[1], d[0] - b[0]) - atan2(b[1] - a[1], b[0] - a[0]))
        turn = (turn + 180) % 360 - 180
        if i:
            s += LineString([c[i - 1], c[i]]).length
        if abs(turn) > CORNER_ANGLE:
            out.append(s)
    return out


def full_length(poly: Polygon) -> bool:
    """A part as long as the whole strip (the motor stick): its ends are the strip ends."""
    return poly.bounds[2] - poly.bounds[0] > SHEET_L - 2 * EDGE


def drop_sheet_ends(paths):
    """Remove cut segments lying on the strip ends (x = 0 or x = SHEET_L): nothing to cut there."""
    def on_end(a, b):
        return (abs(a[0]) < 1e-3 and abs(b[0]) < 1e-3) or (abs(a[0] - SHEET_L) < 1e-3 and abs(b[0] - SHEET_L) < 1e-3)
    out = []
    for p in paths:
        cur = [p[0]]
        for a, b in zip(p, p[1:]):
            if on_end(a, b):
                if len(cur) > 1:
                    out.append(cur)
                cur = [b]
            else:
                cur.append(b)
        if len(cur) > 1:
            out.append(cur)
    return out


def cut_paths_with_tabs(poly: Polygon) -> list[list[tuple[float, float]]]:
    ring = LineString(poly.exterior.coords)
    length = ring.length
    corners = corner_positions(ring)
    n = max(2, round(length / TAB_SPACING))
    half = TAB_W / 2

    def clear(s):
        return (half + 0.1 <= s <= length - half - 0.1
                and all(abs(s - c) > half + 0.5 for c in corners))

    tabs = []
    for k in range(n):
        s0 = (k + 0.5) * length / n
        for step in range(int(length / n / 0.25)):
            s = s0 + (step + 1) // 2 * 0.25 * (1 if step % 2 else -1)  # 0, +.25, -.25, +.5 ...
            if clear(s) and all(abs(s - t) > TAB_W * 3 for t in tabs):
                tabs.append(s)
                break
    if len(tabs) < 2:  # short or jagged outline: put the tabs on the longest straight runs
        segs = sorted(((LineString([a, b]).length, ring.project(Point(a)) + LineString([a, b]).length / 2)
                       for a, b in zip(ring.coords, list(ring.coords)[1:])), reverse=True)
        for seg_len, mid in segs:
            if seg_len > TAB_W + 0.4 and all(abs(mid - t) > TAB_W * 2 for t in tabs):
                tabs.append(mid)
            if len(tabs) >= 2:
                break
    TAB_COUNT.append(len(tabs))
    tabs.sort()
    paths, start = [], 0.0
    for t in tabs:
        paths.append(list(substring(ring, start, t - half).coords))
        start = t + half
    tail = list(substring(ring, start, length).coords)
    if paths:
        paths[0] = tail + paths[0][1:]  # join across the ring start
    else:
        paths.append(tail)
    paths += [list(r.coords) for r in poly.interiors]  # holes: cut through, they are waste
    return drop_sheet_ends(paths) if full_length(poly) else paths


# --------------------------------------------------------------------------
# Engraved part numbers (seven segment glyphs, filled)
# --------------------------------------------------------------------------
SEGMENTS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
            "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def glyphs(text: str, h: float) -> Polygon:
    w, s, gap = 0.6 * h, 0.16 * h, 0.22 * h
    rects = {"a": (0, h - s, w, h), "d": (0, 0, w, s), "g": (0, (h - s) / 2, w, (h + s) / 2),
             "f": (0, h / 2, s, h), "b": (w - s, h / 2, w, h),
             "e": (0, 0, s, h / 2), "c": (w - s, 0, w, h / 2)}
    shapes = [affinity.translate(box(*rects[seg]), i * (w + gap), 0)
              for i, ch in enumerate(text) for seg in SEGMENTS[ch]]
    return unary_union(shapes)


def label_for(poly: Polygon, text: str):
    inner = poly.buffer(-LABEL_MARGIN)
    if inner.is_empty:
        return None
    pin = prep(inner)
    cx, cy = poly.representative_point().coords[0]
    x0, y0, x1, y1 = inner.bounds
    h = DIGIT_MAX_H
    while h >= DIGIT_MIN_H - 1e-9:
        g = glyphs(text, h)
        gw, gh = g.bounds[2], g.bounds[3]
        step = max(0.2, h / 4)
        cands = [(x0 + i * step, y0 + j * step)
                 for i in range(int((x1 - x0 - gw) / step) + 1)
                 for j in range(int((y1 - y0 - gh) / step) + 1)]
        cands.sort(key=lambda p: (p[0] + gw / 2 - cx) ** 2 + (p[1] + gh / 2 - cy) ** 2)
        for x, y in cands:
            if pin.contains(box(x, y, x + gw, y + gh)):
                return affinity.translate(g, x, y)
        h -= 0.2
    return None


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------
def esc_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def svg_path(coords, closed=False) -> str:
    pts = [f"{x:.3f},{SHEET_W - y:.3f}" for x, y in coords]
    return "M " + " L ".join(pts) + (" Z" if closed else "")


def write_svg(path: Path, sheet: Sheet, title: str, raws: dict) -> list[str]:
    """`raws`: part name -> profile in its own coordinates; the placement matrix is
    written into every part group (data-matrix) so sync_all.py can read edits back."""
    warnings = []
    cut, engrave = [], []
    for k, (num, name, poly) in enumerate(sheet.placed):
        base = name.replace(" (vara)", "")
        mat = " ".join(f"{v:.6f}" for v in placement_matrix(raws[base], poly))
        cut.append(f'    <g id="osa{num}-{k}" data-part="{num}" data-name="{esc_attr(name)}" '
                   f'data-matrix="{mat}" data-sheet-w="{SHEET_W:g}"><title>{num}: {name}</title>')
        for c in cut_paths_with_tabs(poly):
            cut.append(f'      <path style="{CUT_STYLE}" d="{svg_path(c)}"/>')
        cut.append("    </g>")
        marks = [affinity.affine_transform(mk, list(placement_matrix(raws[base], poly))) for mk in MARKS.get(base, [])]
        for mk in marks:
            engrave.append(f'    <path style="{ENGRAVE_STYLE}" d="{svg_path(mk.exterior.coords, True)}">'
                           f'<title>{num}: merkki</title></path>')
        free = poly.difference(unary_union(marks).buffer(1.0)) if marks else poly  # number clear of the marks
        if free.geom_type != "Polygon":
            free = max(free.geoms, key=lambda g: g.area)
        lab = label_for_part(name, free, str(num))
        if lab is None:
            warnings.append(num)
            continue
        geoms = getattr(lab, "geoms", [lab])
        d = " ".join(svg_path(r.coords, True) for g in geoms for r in (g.exterior, *g.interiors))
        engrave.append(f'    <path style="{ENGRAVE_STYLE}" d="{d}"><title>{num}</title></path>')
    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'width="{SHEET_L:g}mm" height="{SHEET_W:g}mm" viewBox="0 0 {SHEET_L:g} {SHEET_W:g}">',
        f"  <title>{title}</title>",
        '  <g id="engrave" inkscape:groupmode="layer" inkscape:label="kaiverrus">',
        *engrave,
        "  </g>",
        '  <g id="cut" inkscape:groupmode="layer" inkscape:label="leikkaus">',
        *cut,
        "  </g>",
        "</svg>",
    ]
    path.write_text("\n".join(svg) + "\n")
    return warnings


# --------------------------------------------------------------------------
def main(flat=None, quiet=False) -> list[Path]:
    """Writes the laser SVGs and the overview; returns the written files."""
    if flat is None:
        _, flat, _ = model.build()
    stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    OUT_DIR.mkdir(exist_ok=True)

    parts = [(num, p.name, p.thickness, profile_polygon(p)) for num, p in enumerate(flat, 1)]
    MARKS.clear()
    MARKS.update({p.name: p.marks for p in flat if getattr(p, "marks", None)})
    raws = {p.name: profile_raw(p) for p in flat}
    if not quiet:
        print("Osat:")
        for num, name, t, poly in parts:
            print(f"  {num:3d}  {t:g} mm  {name}")

    written = []
    for t in sorted({p[2] for p in parts}):
        items = [(n, name, poly) for n, name, th, poly in parts if th == t]
        single = t in FILLER
        edge = MARGIN.get(t, EDGE)
        sheets = nest(items, single_sheet=single, edge=edge)
        if t in MARGIN:  # widest gap between the parts that still keeps the sheet count
            for g in (1.5, 2.0, 2.5, 3.0, 4.0):
                wider = nest(items, single_sheet=single, edge=edge, gap=g)
                if len(wider) > len(sheets):
                    break
                sheets = wider
            print(f"{t:g} mm: reunamarginaali {edge:g} mm, osien väli {sheets[0].gap:g} mm")
        if single:
            print()
            for fname, limit in FILLER[t]:
                filler = next(it for it in items if it[1] == fname)
                spares = fill_spares(sheets[0], *filler, limit=limit)
                print(f"{t:g} mm: {spares} ylimääräistä osaa {filler[0]} '{fname}'")
        else:
            print()
        for i, sheet in enumerate(sheets, 1):
            if t in MARGIN:
                spread(sheet)
            name = f"osat{t:g}mm-{stamp}.svg" if single else f"osat{t:g}mm-{i}-{stamp}.svg"
            warnings = write_svg(OUT_DIR / name, sheet, name, raws)
            written.append(OUT_DIR / name)
            used = max(p.bounds[2] for _, _, p in sheet.placed) + sheet.edge
            area = sum(p.area for _, _, p in sheet.placed)
            print(f"  {name}: {len(sheet.placed)} osaa, käytetty pituus {used:.0f} mm, "
                  f"täyttöaste {100 * area / (used * SHEET_W):.0f} % käytetystä alueesta")
            if warnings:
                print(f"    ilman kaiverrettua numeroa (kapeat osat ja siipikaaret): "
                      f"{', '.join(str(n) for n in sorted(set(warnings)))}")
    if TAB_COUNT:
        few = sum(1 for n in TAB_COUNT if n < 2)
        print(f"\nSillat (1 mm): {len(TAB_COUNT)} osaa, vähintään {min(TAB_COUNT)} siltaa / osa"
              + (f" — VAROITUS: {few} osaa alle 2 siltaa" if few else ""))
        TAB_COUNT.clear()
    write_overview(parts, OVERVIEW)
    print(f"\nOsien numeroitu esitys: {OVERVIEW.name}")
    return written + [OVERVIEW]


def write_overview(parts, path: Path):
    """All parts 1:1 in grain orientation, one per row: number, outline, name and size."""
    rows, y, width = [], 4.0, 0.0
    for num, name, t, poly in parts:
        x0, y0, x1, y1 = poly.bounds
        h = max(y1 - y0, 4.0)
        rows.append((num, name, t, affinity.translate(poly, 18 - x0, -y0), y, h, x1 - x0, y1 - y0))
        width = max(width, 18 + x1 - x0 + 90)
        y += h + 4
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}mm" height="{y:.0f}mm" '
         f'viewBox="0 0 {width:.1f} {y:.1f}">',
         f'<rect width="{width:.1f}" height="{y:.1f}" fill="white"/>',
         '<style>text{font-family:sans-serif;fill:#222} .n{font-weight:bold;font-size:4px}'
         ' .t{font-size:3px}</style>']
    for num, name, t, poly, ry, h, w, ph in rows:
        hue = (num * 0.618) % 1
        col = "hsl({:.0f},75%,38%)".format(hue * 360)
        rings = [poly.exterior, *poly.interiors]
        d = " ".join("M " + " L ".join(f"{px:.2f},{ry + h - (py - 0) - (h - ph) / 2:.2f}"
                                       for px, py in r.coords) + " Z" for r in rings)
        o.append(f'<path d="{d}" style="fill:{col};fill-opacity:0.15;stroke:{col};{HAIRLINE}"/>')
        o.append(f'<text class="n" x="14" y="{ry + h / 2 + 1.5:.2f}" text-anchor="end" fill="{col}">{num}</text>')
        o.append(f'<text class="t" x="{18 + w + 4:.1f}" y="{ry + h / 2 + 1:.2f}">'
                 f'{name} — {w:.1f} × {ph:.1f} mm, {t:g} mm balsa</text>')
    o.append("</svg>")
    path.write_text("\n".join(o) + "\n")


if __name__ == "__main__":
    main()
