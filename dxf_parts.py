"""
Read laser cut parts from a DXF sheet as closed polygons (mm).

Laser DXFs have their cut lines broken by tabs (uncut bridges), overlapping
duplicate curves and tiny gaps. This snaps the gaps, merges overlaps, bridges
the tab gaps (end points facing each other along their tangents) and
polygonizes. Parts are numbered top row first, left to right; the same
numbers are used in the overview SVG (write_overview).
"""

import colorsys
import math
from collections import defaultdict
from pathlib import Path

import ezdxf
from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, snap, unary_union

UNIT_MM = {1: 25.4, 4: 1.0, 5: 10.0, 6: 1000.0}  # DXF $INSUNITS -> mm
SNAP_TOL = 0.25  # close micro gaps
MAX_TAB_GAP = 7.0  # longest tab gap to bridge
MIN_AREA = 1.5  # smaller faces are leftovers, not parts
HAIRLINE = "stroke-width:1px;vector-effect:non-scaling-stroke;-inkscape-stroke:hairline"


def _curves(path: Path) -> list[list[tuple[float, float]]]:
    doc = ezdxf.readfile(path)
    s = UNIT_MM.get(doc.header.get("$INSUNITS", 4), 1.0)
    return [[(p[0] * s, p[1] * s) for p in e.flattening(0.01 / s)] for e in doc.modelspace()]


def _network(curves):
    lines = [LineString(c) for c in curves if len(c) > 1]
    allg = unary_union(lines)
    allg = snap(allg, allg, SNAP_TOL)
    net = linemerge(unary_union(allg))
    return list(net.geoms) if hasattr(net, "geoms") else [net]


def _bridges(segs):
    ends = defaultdict(list)
    for s in segs:
        c = list(s.coords)
        if c[0] == c[-1]:
            continue
        ends[(round(c[0][0], 2), round(c[0][1], 2))].append((c[0], c[1]))
        ends[(round(c[-1][0], 2), round(c[-1][1], 2))].append((c[-1], c[-2]))
    free = [v[0] for v in ends.values() if len(v) == 1]
    cand = []
    for a, (p, pp) in enumerate(free):
        t = (p[0] - pp[0], p[1] - pp[1])
        tl = math.hypot(*t) or 1
        for b in range(a + 1, len(free)):
            q, qq = free[b]
            d = math.dist(p, q)
            if d > MAX_TAB_GAP or d < 1e-9:
                continue
            u = (q[0] - qq[0], q[1] - qq[1])
            ul = math.hypot(*u) or 1
            v = ((q[0] - p[0]) / d, (q[1] - p[1]) / d)
            ca = (t[0] * v[0] + t[1] * v[1]) / tl
            cb = -(u[0] * v[0] + u[1] * v[1]) / ul
            if ca > 0.9 and cb > 0.9:
                cand.append((d - 2 * (ca + cb), a, b, p, q))
    used, out = set(), []
    for _, a, b, p, q in sorted(cand):
        if a not in used and b not in used:
            used |= {a, b}
            out.append(LineString([p, q]))
    return out


def load_parts(path) -> tuple[list[Polygon], list[LineString]]:
    """Closed parts (numbered from 1 = index + 1) and the merged line network."""
    segs = _network(_curves(Path(path)))
    faces = sorted(polygonize(unary_union(segs + _bridges(segs))), key=lambda f: -f.area)
    parts = []
    for f in faces:
        rp = f.representative_point()
        parent = [p for p in parts if p[0].contains(rp)]
        if parent:
            parent[-1][1].append(f)
        else:
            parts.append((f, []))
    polys = [Polygon(o.exterior.coords, [h.exterior.coords for h in hs]) for o, hs in parts]
    polys = [p for p in polys if p.area > MIN_AREA]
    polys.sort(key=lambda p: (-round(p.bounds[3] / 6), p.bounds[0]))
    return polys, segs


def normalized(poly: Polygon, mirror_x=False) -> Polygon:
    """Part moved to the origin (bbox min = 0,0), optionally mirrored along X."""
    if mirror_x:
        poly = affinity.scale(poly, -1, 1, origin=(0, 0))
    x0, y0, _, _ = poly.bounds
    return affinity.translate(poly, -x0, -y0)


def write_overview(path, out_svg):
    """Numbered, colored overview of the DXF parts; hover a number for its size."""
    polys, segs = load_parts(path)
    x0 = min(p.bounds[0] for p in polys) - 4
    x1 = max(p.bounds[2] for p in polys) + 4
    y0 = min(p.bounds[1] for p in polys) - 4
    y1 = max(p.bounds[3] for p in polys) + 4
    w, h = x1 - x0, y1 - y0

    def col(n):
        r, g, b = colorsys.hsv_to_rgb((n * 0.618) % 1, 0.9, 0.75)
        return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"

    def pts(coords):
        return " ".join(f"{x:.2f},{-y:.2f}" for x, y in coords)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * 4:.0f}" height="{h * 4:.0f}" '
         f'viewBox="{x0:.2f} {-y1:.2f} {w:.2f} {h:.2f}">',
         f'<rect x="{x0:.2f}" y="{-y1:.2f}" width="{w:.2f}" height="{h:.2f}" fill="white"/>']
    o += [f'<polyline style="fill:none;stroke:#bbb;{HAIRLINE}" points="{pts(s.coords)}"/>' for s in segs]
    for n, p in enumerate(polys, 1):
        o.append(f'<polygon style="fill:{col(n)};fill-opacity:0.12;stroke:{col(n)};{HAIRLINE}" '
                 f'points="{pts(p.exterior.coords)}"/>')
    for n, p in enumerate(polys, 1):
        x, y = p.representative_point().coords[0]
        bw, bh = p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]
        o.append(f'<text x="{x:.2f}" y="{-y + 1:.2f}" font-family="sans-serif" font-weight="bold" '
                 f'font-size="3" text-anchor="middle" fill="{col(n)}">'
                 f'{n}<title>{n}: {bw:.1f} x {bh:.1f} mm</title></text>')
    o.append("</svg>")
    Path(out_svg).write_text("\n".join(o) + "\n")
    return polys
