"""
A0 general arrangement drawing ILT-P18-001 (Iltatähti P-18) of the
p18_iltatahti.py model.

One A0 sheet (1189 x 841 mm, landscape), main views 1:1, enlarged details,
3D views of the trim settings (incidence, wash-in, stab tilt, rudder, thrust
line), shim table, the combined texts of the US P-18 plans, parts list,
technical data, notes, revision and title block. Written as SVG (mm units,
prints 1:1) and PDF (vector, via cairosvg).

The views are hidden-line projections of the very same 3D model the laser
files are cut from; part numbers are the laser engraving numbers.

Run:  .venv/bin/python drawing.py      (also run by p18_iltatahti.py)
"""

import re
from datetime import date
from math import atan, atan2, cos, degrees, hypot, radians, sin, tan
from pathlib import Path

import cairosvg
from build123d import Axis, Box, Compound, Cylinder, GeomType, Location, Plane, Vector, extrude

import p18_iltatahti as m

OUT_DIR = Path(__file__).parent / "piirustus"
DRAWING_NO = "ILT-P18-001"
MODEL_NAME = "ILTATÄHTI P-18"
REVISION = "A"
AUTHOR = "J. Juslin, DI"
TODAY = date.today()

W, H = 1189.0, 841.0  # A0 landscape
FRAME = (20.0, 10.0, W - 10.0, H - 10.0)  # ISO 5457: 20 mm filing margin on the left
FONT = "DejaVu Sans"
THICK, THIN = 0.5, 0.25  # ISO 128 line widths
TXT, TXT_S, TXT_L = 3.5, 2.5, 5.0


def fmt(v: float, dec: int = 1) -> str:
    """Finnish number format: integers without decimals, decimal comma."""
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.{dec}f}".replace(".", ",")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# SVG sheet primitives
# --------------------------------------------------------------------------
class Sheet:
    def __init__(self):
        self.el: list[str] = []
        self.defs: list[str] = []
        self.texts: list[tuple] = []  # (x0, y0, x1, y1, text) estimated, for the layout check

    def add(self, s: str):
        self.el.append(s)

    def path(self, d: str, w=THIN, dash=None, fill="none", extra="", color="#000"):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{w}" '
                 f'stroke-linecap="round" stroke-linejoin="round"{da}{extra}/>')

    def line(self, a, b, w=THIN, dash=None):
        self.path(f"M{a[0]:.3f},{a[1]:.3f} L{b[0]:.3f},{b[1]:.3f}", w, dash)

    def poly(self, pts, w=THIN, closed=False, fill="none", dash=None):
        d = "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts) + (" Z" if closed else "")
        self.path(d, w, dash, fill)

    def rect(self, x, y, w_, h_, w=THIN, fill="none"):
        self.add(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w_:.3f}" height="{h_:.3f}" fill="{fill}" '
                 f'stroke="#000" stroke-width="{w}"/>')

    def circle(self, c, r, w=THIN, fill="white"):
        self.add(f'<circle cx="{c[0]:.3f}" cy="{c[1]:.3f}" r="{r:.3f}" fill="{fill}" stroke="#000" '
                 f'stroke-width="{w}"/>')

    def text(self, x, y, s, size=TXT, anchor="start", rot=0.0, bold=False, italic=False, fill="#000"):
        w_ = 0.57 * size * len(s) * (1.08 if bold else 1.0)
        dx0 = {"start": 0.0, "middle": -w_ / 2, "end": -w_}[anchor]
        if abs(abs(rot) - 90) < 1:  # vertical text, reading upwards
            self.texts.append((x - size, y - dx0 - w_, x + 0.3, y - dx0, s))
        elif abs(rot) < 1:
            self.texts.append((x + dx0, y - size * 0.8, x + dx0 + w_, y + size * 0.22, s))
        tr = f' transform="rotate({rot:.2f} {x:.3f} {y:.3f})"' if rot else ""
        fw = ' font-weight="bold"' if bold else ""
        fs = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.3f}" y="{y:.3f}" font-family="{FONT}" font-size="{size}" '
                 f'text-anchor="{anchor}" fill="{fill}"{fw}{fs}{tr}>{esc(s)}</text>')

    def arrow(self, tip, direction, length=2.5, half=0.55):
        """Filled ISO arrowhead, `direction` points from the tail to the tip."""
        dx, dy = direction
        n = hypot(dx, dy) or 1
        dx, dy = dx / n, dy / n
        b = (tip[0] - dx * length, tip[1] - dy * length)
        p1 = (b[0] - dy * half, b[1] + dx * half)
        p2 = (b[0] + dy * half, b[1] - dx * half)
        self.poly([tip, p1, p2], w=0.1, closed=True, fill="#000")

    def svg(self) -> str:
        return "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:g}mm" height="{H:g}mm" '
            f'viewBox="0 0 {W:g} {H:g}">',
            f"<title>{DRAWING_NO} {REVISION} {MODEL_NAME}</title>",
            "<defs>", *self.defs, "</defs>",
            f'<rect x="0" y="0" width="{W:g}" height="{H:g}" fill="white"/>',
            *self.el,
            "</svg>",
        ])


# --------------------------------------------------------------------------
# Dimensioning (ISO 129 style)
# --------------------------------------------------------------------------
def dim(sh: Sheet, p1, p2, dist: float, text: str, size=TXT_S, ext_gap=1.0, ext_over=1.5):
    """Aligned linear dimension between sheet points p1 and p2.

    The dimension line is `dist` mm off the p1->p2 line, to the left of the
    direction p1->p2 for positive dist (in sheet coordinates, y down).
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = hypot(dx, dy)
    if L < 1e-6:
        return
    ux, uy = dx / L, dy / L
    nx, ny = uy, -ux  # left normal on the sheet (y down)
    s = 1 if dist >= 0 else -1
    a = (p1[0] + nx * dist, p1[1] + ny * dist)
    b = (p2[0] + nx * dist, p2[1] + ny * dist)
    for p, q in ((p1, a), (p2, b)):
        sx, sy = p[0] + nx * ext_gap * s, p[1] + ny * ext_gap * s
        ex, ey = q[0] + nx * ext_over * s, q[1] + ny * ext_over * s
        sh.line((sx, sy), (ex, ey))
    tw = 0.6 * size * len(text)
    if L > 7:
        sh.line(a, b)
        sh.arrow(a, (-ux, -uy))
        sh.arrow(b, (ux, uy))
    else:  # short: arrows from outside
        sh.line((a[0] - ux * 5, a[1] - uy * 5), (b[0] + ux * 5, b[1] + uy * 5))
        sh.arrow(a, (ux, uy))
        sh.arrow(b, (-ux, -uy))
    ang = degrees(atan2(uy, ux))
    if ang > 90.01 or ang <= -90:
        ang -= 180 if ang > 0 else -180
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    # text above the line (the side away from the object)
    tx, ty = mx + nx * s * 0.9, my + ny * s * 0.9
    if s < 0 or (abs(ang) < 1 and ny * s > 0):
        pass
    off = 0.9 if (ny * s) < 0 or abs(ny) < 1e-9 else 0.9 + size * 0.75
    tx, ty = mx + nx * s * off, my + ny * s * off
    if L <= 7 and tw > L - 1:
        tx, ty = b[0] + ux * (6 + tw / 2), b[1] + uy * (6 + tw / 2) - 0.8
    sh.text(tx, ty, text, size=size, anchor="middle", rot=ang)


def dim_h(sh, x1, x2, y_feat1, y_feat2, y_line, text, size=TXT_S):
    """Horizontal dimension: features at (x1, y_feat1), (x2, y_feat2), line at y_line."""
    sx = 1 if y_line < min(y_feat1, y_feat2) else -1  # above: extension lines go up
    for x, yf in ((x1, y_feat1), (x2, y_feat2)):
        sh.line((x, yf - sx * 1.0), (x, y_line - sx * 1.5))
    _dimline(sh, (x1, y_line), (x2, y_line), text, size, above=True)


def dim_v(sh, y1, y2, x_feat1, x_feat2, x_line, text, size=TXT_S):
    """Vertical dimension: features at (x_feat1, y1), (x_feat2, y2), line at x_line."""
    sx = 1 if x_line > max(x_feat1, x_feat2) else -1
    for y, xf in ((y1, x_feat1), (y2, x_feat2)):
        sh.line((xf + sx * 1.0, y), (x_line + sx * 1.5, y))
    _dimline(sh, (x_line, y1), (x_line, y2), text, size, above=True, vertical=True)


def _dimline(sh, a, b, text, size, above=True, vertical=False):
    L = hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-6:
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    tw = 0.58 * size * len(text)
    if L >= 7:
        sh.line(a, b)
        sh.arrow(a, (-ux, -uy))
        sh.arrow(b, (ux, uy))
    else:
        sh.line((a[0] - ux * 4, a[1] - uy * 4), (b[0] + ux * 4, b[1] + uy * 4))
        sh.arrow(a, (ux, uy))
        sh.arrow(b, (-ux, -uy))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if vertical:
        if L >= tw + 2:
            sh.text(mx - 0.9, my, text, size=size, anchor="middle", rot=-90)
        else:  # text beside the arrow end
            sh.text(mx - 0.9, min(a[1], b[1]) - 5 - tw / 2, text, size=size, anchor="middle", rot=-90)
    else:
        if L >= tw + 2:
            sh.text(mx, my - 0.9, text, size=size, anchor="middle")
        else:
            sh.text(max(a[0], b[0]) + 5 + tw / 2, my - 0.9, text, size=size, anchor="middle")


def dim_chain_h(sh, xs, y_feats, y_line, size=TXT_S):
    """Chain of horizontal dimensions between consecutive xs (sorted)."""
    for (x1, f1), (x2, f2) in zip(zip(xs, y_feats), zip(xs[1:], y_feats[1:])):
        dim_h(sh, x1, x2, f1, f2, y_line, fmt(abs(x2 - x1)), size)


def angle_dim(sh, c, r, a1, a2, text, size=TXT_S):
    """Angular dimension: arc of radius r around sheet point c from angle a1 to a2
    (degrees, sheet coordinates: 0 = +x, positive = clockwise on the sheet)."""
    n = 24
    pts = [(c[0] + r * cos(radians(a1 + (a2 - a1) * k / n)), c[1] + r * sin(radians(a1 + (a2 - a1) * k / n)))
           for k in range(n + 1)]
    sh.poly(pts)
    for ang, sgn, p in ((a1, -1, pts[0]), (a2, 1, pts[-1])):
        t = radians(ang)
        tang = (-sin(t) * sgn, cos(t) * sgn)
        sh.arrow(p, tang, length=2.0, half=0.45)
    am = radians((a1 + a2) / 2)
    sh.text(c[0] + (r + 2.5) * cos(am) + 4, c[1] + (r + 2.5) * sin(am) + 1, text, size=size, anchor="start")


def leader(sh, tip, text_pos, lines, size=TXT_S, dot=False, anchor=None):
    """Leader from a feature to a note. `lines`: list of text lines."""
    sh.line(tip, text_pos)
    if dot:
        sh.circle(tip, 0.45, w=0.1, fill="#000")
    else:
        sh.arrow(tip, (tip[0] - text_pos[0], tip[1] - text_pos[1]))
    right = text_pos[0] >= tip[0] if anchor is None else anchor == "start"
    shoulder = (text_pos[0] + (3 if right else -3), text_pos[1])
    sh.line(text_pos, shoulder)
    x = shoulder[0] + (0.8 if right else -0.8)
    for k, s in enumerate(lines):
        sh.text(x, text_pos[1] + 1.0 + k * (size + 1.0), s, size=size, anchor="start" if right else "end")


def balloon(sh, tip, pos, label, r=3.6, arrow=False):
    """Item balloon (part number) with a leader ending in a dot, or an arrow, on the part."""
    dx, dy = tip[0] - pos[0], tip[1] - pos[1]
    d = hypot(dx, dy) or 1
    start = (pos[0] + dx / d * r, pos[1] + dy / d * r)
    sh.line(start, tip, w=0.3 if arrow else THIN)
    if arrow:
        sh.arrow(tip, (dx, dy), length=3.0, half=0.7)
    else:
        sh.circle(tip, 0.5, w=0.1, fill="#000")
    sh.circle(pos, r, w=0.35 if arrow else THIN)
    size = (3.2 if len(label) < 3 else 2.4) * (r / 3.6) ** 0.5
    sh.text(pos[0], pos[1] + size * 0.36, label, size=size, anchor="middle", bold=True)


def view_title(sh, x, y, title, scale, sub=None):
    sh.text(x, y, title, size=TXT_L, anchor="middle", bold=True)
    tw = 0.62 * TXT_L * len(title)
    sh.line((x - tw / 2, y + 1.2), (x + tw / 2, y + 1.2), w=THIN)
    sh.text(x, y + 5.5, f"MITTAKAAVA {scale}" + (f" — {sub}" if sub else ""), size=TXT_S, anchor="middle")


# --------------------------------------------------------------------------
# Views: hidden line projections placed on the sheet
# --------------------------------------------------------------------------
class View:
    def __init__(self, shapes, direction, up, scale=1.0, hidden=False):
        """direction: from the object towards the viewer (camera side)."""
        self.shapes = [s for s in shapes if s is not None]
        self.N = Vector(direction).normalized()
        up = Vector(up)
        self.X = up.cross(self.N).normalized()
        self.Y = self.N.cross(self.X).normalized()
        self.scale = scale
        self.hidden = hidden
        comp = Compound(self.shapes)
        vis, hid = comp.project_to_viewport(tuple(self.N * 2000), tuple(self.Y), look_at=(0, 0, 0))
        self.vis = [self._pts(e) for e in vis]
        self.hid = [self._pts(e) for e in hid] if hidden else []
        xs = [p[0] for e in self.vis for p in e]
        ys = [p[1] for e in self.vis for p in e]
        self.bb = (min(xs), min(ys), max(xs), max(ys))
        self.ox = self.oy = 0.0

    @staticmethod
    def _pts(e):
        if e.geom_type == GeomType.LINE:
            ps = [e.position_at(0), e.position_at(1)]
        else:
            n = max(6, int(e.length / 0.4))
            ps = [e.position_at(k / n) for k in range(n + 1)]
        return [(p.X, p.Y) for p in ps]

    def proj(self, P):
        P = Vector(P)
        return P.dot(self.X), P.dot(self.Y)

    @property
    def size(self):
        return ((self.bb[2] - self.bb[0]) * self.scale, (self.bb[3] - self.bb[1]) * self.scale)

    def fit(self, max_w: float, max_h: float = 1e9):
        """Shrink the scale if needed so that the view fits max_w x max_h."""
        w = (self.bb[2] - self.bb[0]) or 1
        h = (self.bb[3] - self.bb[1]) or 1
        self.scale = min(self.scale, max_w / w, max_h / h)
        return self

    def place(self, cx, cy):
        """Center the view's bounding box at sheet point (cx, cy)."""
        self.ox = cx - (self.bb[0] + self.bb[2]) / 2 * self.scale
        self.oy = cy + (self.bb[1] + self.bb[3]) / 2 * self.scale
        return self

    def place_tl(self, x, y):
        """Top left corner of the view's bounding box at sheet point (x, y)."""
        self.ox = x - self.bb[0] * self.scale
        self.oy = y + self.bb[3] * self.scale
        return self

    def s2(self, x, y):
        return self.ox + x * self.scale, self.oy - y * self.scale

    def at(self, P):
        """Sheet position of a 3D model point."""
        return self.s2(*self.proj(P))

    def sheet_bb(self):
        x0, y0 = self.s2(self.bb[0], self.bb[3])
        x1, y1 = self.s2(self.bb[2], self.bb[1])
        return x0, y0, x1, y1

    def draw(self, sh: Sheet, w=THICK):
        def d(edges):
            return " ".join("M" + " L".join("{:.3f},{:.3f}".format(*self.s2(x, y)) for x, y in e)
                            for e in edges if len(e) > 1)
        if self.hid:  # hidden edges: thin, grey, dashed
            sh.path(d(self.hid), w=0.15, dash="1.6 1.0", color="#777")
        sh.path(d(self.vis), w=w)


def crop(shapes, lo, hi):
    """Parts of the shapes inside the box lo..hi (for cut-away details)."""
    lo, hi = Vector(lo), Vector(hi)
    box = Location((lo + hi) / 2) * Box(*(hi - lo))
    out = []
    for s in shapes:
        r = s & box
        if r is not None and r.volume > 1e-6:
            out.append(r)
    return out


# --------------------------------------------------------------------------
# Sheet furniture: frame, zones, title block
# --------------------------------------------------------------------------
def frame(sh: Sheet):
    x0, y0, x1, y1 = FRAME
    sh.rect(0.5, 0.5, W - 1, H - 1, w=0.18)  # trimming edge
    sh.rect(x0, y0, x1 - x0, y1 - y0, w=0.7)
    # grid reference zones (ISO 5457): 12 columns 1..12, 8 rows A..H
    cols, rows = 16, 12
    for k in range(cols + 1):
        x = x0 + (x1 - x0) * k / cols
        sh.line((x, y0), (x, y0 - 5 if y0 > 6 else 1), w=THIN)
        sh.line((x, y1), (x, y1 + 5), w=THIN)
    for k in range(cols):
        x = x0 + (x1 - x0) * (k + 0.5) / cols
        sh.text(x, y0 - 2.5, str(k + 1), size=TXT_S, anchor="middle")
        sh.text(x, y1 + 6.2, str(k + 1), size=TXT_S, anchor="middle")
    for k in range(rows + 1):
        y = y0 + (y1 - y0) * k / rows
        sh.line((x0, y), (x0 - 5, y), w=THIN)
        sh.line((x1, y), (x1 + 5, y), w=THIN)
    for k in range(rows):
        y = y0 + (y1 - y0) * (k + 0.5) / rows + 1
        sh.text(x0 - 3.5, y, "ABCDEFGHJKLM"[k], size=TXT_S, anchor="middle")
        sh.text(x1 + 5, y, "ABCDEFGHJKLM"[k], size=TXT_S, anchor="middle")
    # centring marks
    for x, y, dx, dy in ((W / 2, 0, 0, 1), (W / 2, H, 0, -1), (0, H / 2, 1, 0), (W, H / 2, -1, 0)):
        sh.line((x, y), (x + dx * 12, y + dy * 12), w=0.7)


def projection_symbol(sh, x, y, s=1.0):
    """ISO first angle (method E) projection symbol, lower left corner at x, y."""
    # truncated cone side view (right) and end view (left) in first angle
    # first angle: cone elevation on the left (small end left), end view circles on the right
    sh.poly([(x, y - 4 * s), (x + 10 * s, y - 2 * s), (x + 10 * s, y - 12 * s), (x, y - 10 * s)],
            w=THIN, closed=True)
    sh.circle((x + 19 * s, y - 7 * s), 5 * s, w=THIN, fill="none")
    sh.circle((x + 19 * s, y - 7 * s), 3 * s, w=THIN, fill="none")
    sh.line((x - 2 * s, y - 7 * s), (x + 26 * s, y - 7 * s), w=0.18, dash="5 1 1 1")


def title_block(sh: Sheet, x, y, w):
    """Title block with the bottom right corner at the frame corner; returns its top y."""
    rows = [  # (height, cells [(width fraction, label, value, value size, bold)])
        (7, [(0.5, "NIMITYS", "", 0, False), (0.5, "", "", 0, False)]),
    ]
    h_total = 62
    top = y - h_total
    sh.rect(x, top, w, h_total, w=0.7)
    # model name block (left, large)
    lw = w * 0.52
    sh.line((x + lw, top), (x + lw, y), w=0.5)
    sh.text(x + 3, top + 6, "NIMITYS", size=2.0)
    sh.text(x + 3, top + 19, MODEL_NAME, size=10, bold=True)
    sh.text(x + 3, top + 25.5, "Kumimoottorikäyttöinen sisälennokki", size=TXT)
    sh.line((x, top + 29), (x + lw, top + 29), w=THIN)
    sh.text(x + 3, top + 33.5, "PIIRUSTUS", size=2.0)
    sh.text(x + 3, top + 40.5, "Yleispiirustus ja rakenne", size=4.2, bold=True)
    sh.text(x + 3, top + 46, "Kokoonpano, trimmaus, detaljit, osaluettelo", size=TXT_S)
    sh.line((x, top + 49), (x + lw, top + 49), w=THIN)
    sh.text(x + 3, top + 53.5, "TIEDOSTOT", size=2.0)
    sh.text(x + 3, top + 58.5, "p18_iltatahti.py · step/iltatahti_p18.step · laser/osat*.svg", size=2.2)
    # right: people and data grid
    rx = x + lw
    rw = w - lw
    names = [("SUUNNITELLUT", AUTHOR, TODAY.strftime("%d.%m.%Y")),
             ("PIIRTÄNYT", AUTHOR, TODAY.strftime("%d.%m.%Y")),
             ("TARKASTANUT", "", ""),
             ("HYVÄKSYNYT", AUTHOR, TODAY.strftime("%d.%m.%Y"))]
    rh = 6.5
    c1, c2 = rx + 25, rx + rw - 20
    for k, (lab, who, when) in enumerate(names):
        yy = top + k * rh
        sh.line((rx, yy + rh), (rx + rw, yy + rh), w=THIN)
        sh.text(rx + 1.5, yy + 4.4, lab, size=2.2)
        sh.text(c1 + 1.5, yy + 4.6, who, size=3.0, bold=bool(who))
        sh.text(c2 + 1.5, yy + 4.6, when, size=2.6)
    sh.line((c1, top), (c1, top + 4 * rh), w=THIN)
    sh.line((c2, top), (c2, top + 4 * rh), w=THIN)
    gy = top + 4 * rh
    cells = [("MITTAKAAVA", "1:1"), ("KOKO", "A0"), ("YKSIKÖT", "mm"), ("ARKKI", "1 / 1")]
    cw = rw / 4
    for k, (lab, val) in enumerate(cells):
        cx = rx + k * cw
        if k:
            sh.line((cx, gy), (cx, gy + 13), w=THIN)
        sh.text(cx + 1.5, gy + 3.8, lab, size=2.0)
        sh.text(cx + cw / 2, gy + 10.5, val, size=4.5, anchor="middle", bold=True)
    sh.line((rx, gy + 13), (rx + rw, gy + 13), w=THIN)
    ny = gy + 13
    sh.text(rx + 1.5, ny + 3.8, "PIIRUSTUSNUMERO", size=2.0)
    sh.text(rx + 3, ny + 12.5, DRAWING_NO, size=7, bold=True)
    sh.line((rx + rw - 16, ny), (rx + rw - 16, y), w=THIN)
    sh.text(rx + rw - 14.5, ny + 3.8, "REV", size=2.0)
    sh.text(rx + rw - 8, ny + 13, REVISION, size=8, anchor="middle", bold=True)
    sh.line((rx, ny + 16), (rx + rw - 16, ny + 16), w=THIN)
    projection_symbol(sh, rx + 3, y - 2.2, s=0.62)
    sh.text(rx + 20, y - 4, "PROJEKTIO ISO-E (1. kulma)", size=2.0)
    return top


def revision_block(sh, x, y_bottom, w):
    rows = [("A", TODAY.strftime("%d.%m.%Y"), "Ensimmäinen julkaisu", "JJ", "JJ")]
    h = 5.0
    top = y_bottom - h * (len(rows) + 1)
    sh.rect(x, top, w, y_bottom - top, w=0.5)
    cols = [("REV", 0.08), ("PVM", 0.18), ("MUUTOS", 0.54), ("PIIRT.", 0.10), ("HYV.", 0.10)]
    cx = x
    for lab, f in cols:
        sh.text(cx + 1.2, top + 3.6, lab, size=2.2, bold=True)
        cx += w * f
        if cx < x + w - 0.1:
            sh.line((cx, top), (cx, y_bottom), w=THIN)
    for k, r in enumerate(rows):
        yy = top + h * (k + 1)
        sh.line((x, yy), (x + w, yy), w=THIN)
        cx = x
        for (lab, f), val in zip(cols, r):
            sh.text(cx + 1.2, yy + 3.6, val, size=2.5)
            cx += w * f
    return top


def table(sh, x, y, widths, header, rows, row_h=4.6, size=2.5, title=None):
    """Simple ruled table; returns the bottom y."""
    w = sum(widths)
    if title:
        sh.text(x, y - 1.5, title, size=TXT, bold=True)
    n = len(rows) + 1
    sh.rect(x, y, w, n * row_h, w=0.5)
    cx = x
    for wd in widths[:-1]:
        cx += wd
        sh.line((cx, y), (cx, y + n * row_h), w=THIN)
    for k, row in enumerate([header] + rows):
        yy = y + k * row_h
        if k:
            sh.line((x, yy), (x + w, yy), w=THIN if k > 1 else 0.5)
        cx = x
        for wd, val in zip(widths, row):
            anchor = "middle" if wd < 14 else "start"
            tx = cx + wd / 2 if anchor == "middle" else cx + 1.2
            sh.text(tx, yy + row_h - 1.25, str(val), size=size, anchor=anchor, bold=(k == 0))
            cx += wd
    return y + n * row_h


# --------------------------------------------------------------------------
# Parts list from the model (numbers = laser engraving numbers)
# --------------------------------------------------------------------------
def parts_list(flat):
    groups = {}
    side_fi = {"L": "vasen", "R": "oikea"}

    def name_of(n):
        mt = re.match(r"wing_([LR])_(le|te)_spar", n)
        if mt:
            return ("Siiven " + ("etureunarima" if mt[2] == "le" else "jättöreunarima") + f", {side_fi[mt[1]]}")
        mt = re.match(r"wing_[LR]_rib(\d)_(\d+)", n)
        if mt:
            k = int(mt[1])
            return ["Tyvikaari", "Täysikaari (keskiriman lovi)"][k] if k < 2 else "Siipikaari"
        if "center_spar" in n:
            return "V-kulman keskirima"
        if "leg_front" in n:
            return "Siipisatulan etutuki"
        if "leg_rear" in n:
            return "Siipisatulan takatuki"
        if n.startswith("stab_le"):
            return "Korkeusvakaajan etureunarima"
        if n.startswith("stab_te"):
            return "Korkeusvakaajan jättöreunarima"
        if n.startswith("stab_rib"):
            return "Korkeusvakaajan kaari"
        return {"fin_le": "Sivuperäsin, johtoreuna + akseli", "fin_root": "Sivuperäsin, alarima",
                "fin_top": "Sivuperäsin, ylärima", "fin_te": "Sivuperäsin, jättöreuna",
                "motor_stick": "Runkotikku", "wing_wedge": "Kohtauskulmakiila 2°"}.get(n, n)

    for num, p in enumerate(flat, 1):
        b = p.profile.bounding_box()
        size = f"{fmt(b.size.X)}×{fmt(b.size.Y)}×{fmt(p.thickness)}"
        key = (name_of(p.name), size, p.thickness)
        groups.setdefault(key, []).append(num)

    def ranges(nums):
        out, start, prev = [], nums[0], nums[0]
        for n in nums[1:] + [None]:
            if n is not None and n == prev + 1:
                prev = n
                continue
            out.append(f"{start}" if start == prev else f"{start}–{prev}" if prev > start + 1 else f"{start}, {prev}")
            if n is not None:
                start = prev = n
        return ", ".join(out)

    rows = [[ranges(nums), name, len(nums), size, f"Balsa {fmt(t)} mm"]
            for (name, size, t), nums in sorted(groups.items(), key=lambda kv: kv[1][0])]
    n0 = len(flat)
    mb = m.pukki.build_mount(m.PUKKI).bounding_box()
    rows += [[str(n0 + 1), "Moottoripukki (pukki.py, step/pukki.stl)", 1,
              f"{fmt(mb.size.X)}×{fmt(mb.size.Y)}×{fmt(mb.size.Z)}", "PLA, 3D-tulostus"],
             [str(n0 + 2), "Takakoukku", 1, "⌀0,8", "Pianolanka"],
             [str(n0 + 3), "Potkuri 6\" (havainnekuva)", 1, "⌀152", "Kaupallinen, muovi"]]
    return rows


# --------------------------------------------------------------------------
# Texts of the US P-18 plans in this directory, combined (original language).
# Rules are given once; "inspired by" remarks are left out.
# --------------------------------------------------------------------------
US_TEXTS = [
    ("P-18 RULES (AMA EVENT 227) — Big Smash, P-18 Pursuit, P-18 Cruiser", [
        "1. Except for specific rules that apply to this event, the rules for free flight",
        "   rubber hand launch stick shall apply.",
        "2. The model airplane shall be a rubber powered monoplane covered with either",
        "   tissue or HDPE plastic shopping bag (produce bag) material.",
        "3. The wing shall not exceed 4.5 inch chord and projected span of 18 inches.",
        "4. Horizontal stabilizer: maximum span 9 inches, maximum chord 3.5 inches.",
        "5. Maximum overall length, including the propeller, 18 inches.",
        "6. The propeller shall be an unmodified commercially available plastic prop with a",
        "   nominally maximum diameter of 6\". If the propeller is advertised as being a 6\" unit,",
        "   it is acceptable (Pursuit / Cruiser: max 5.5\"). Weight may be added to one blade",
        "   for balancing.",
        "7. The maximum hook to hook distance shall not exceed 10 inches.",
        "8. The minimum weight of the completed model, less rubber, shall be 7.5 grams.",
        "9. No limits on rubber motor.",
    ]),
    ("BIG SMASH P-18 (EAA Indoor 2020)", [
        "Wing main spars ~ firm 3/32. Wing tip spars ~ firm 1/16. Wing ribs ~ medium 1/16,",
        "sliced x 1/16 deep. 6% arc wing foil — same template for stab.",
        "Stab spars ~ firm 1/16. Stab ribs ~ medium 1/16 sliced x 1/16 deep (use same template as wing).",
        "1.63 dihedral each tip (double poly dihedral optional, maintain 18\" max span). Left wing tip.",
        "Wing posts ~ firm 3/32 x 3\" long, paper sockets. Wing posts offset .5\".",
        "Rudders ~ all medium 1/16 (build two!). Rudders attach to top of ribs. Attach rudders at",
        "leading edge so that trailing edge does not extend beyond 18\".",
        "Motor stick ~ firm 3/16 or 1/8 x 3/8 tall x 10.5 long. Taper ends.",
        "Tailboom ~ firm 3/32 tapered from 1/4\" to 1/8\". Overlap glue seam to stay under 18\" O.A.L.",
        "Prop and hangar ~ any commercial 6\" plastic prop. Hangar up to builder!",
        "Wood sizes are suggestions. Feel free to change!",
        "Covering suggestion is plastic veggie bag adhered with glue stick.",
    ]),
    ("P-18 PURSUIT (design/drawn D. R. Higgins, 10-29-2018)", [
        "Model weights: wing assy 2.2 g, stabilizer 0.8 g, propeller 2.0 g, motor stick 2.5 g,",
        "total weight 7.5 g.",
        "Wing: 1/16\" sq. L.E. 10 lb/cu.ft, 1/16\" sq. T.E. 8 lb/cu.ft, rib (10 places), 1/16\" sq. brace",
        "(8 places), tip plate (2 places) — make 2 from 1/32\" thk. soft balsa.",
        "Wing assembly: build and cover each wing panel separately before gluing the two wing",
        "panels together. 5° (ref), 3/4\" dihedral. Cant ribs outboard using tool shown.",
        "Rib canting tool: make from 1/8\" thk. scrap balsa wood.",
        "Rib template: 10.1\" radius. Make from 1/16\" thick plywood or 1/32\" thick aluminum sheet",
        "metal. Make ribs from 1/16\" thk. light \"C\" grain balsa.",
        "Forward wing post: make from 1/16\" sq. ultra hard balsa or basswood. Glue to inside of",
        "leading edge and rib at 90 degree angle, then glue the gusset to L.E. and post.",
        "Aft wing post: make from 1/16\" sq. ultra hard balsa or basswood. Glue to inside of trailing",
        "edge and rib at offset dimension shown, then glue the gusset to T.E. and post.",
        "Rear view of wing assembly: aft wing post offset 0.10\"/0.12\" for left wing wash-in.",
        "Gusset: make from 1/16\" thick hard scrap balsa (typ. 2 places).",
        "Stabilizer: 1/16\" sq. L.E. and T.E. 8 lb/cu.ft, rib (5 places), 1/16\" sq. brace (4 places).",
        "Forward / aft stab post: make from 1/16\" sq. hard balsa stick, glue to L.E. / T.E. and rib.",
        "Stab tip plate: make 2 from 1/32\" thk. soft balsa. Rudder 1/16\" sq. Trim tab: cut from plan.",
        "Motor stick: make from 1/8\" x 3/8\" x 17.1\" hard balsa stick, straight taper from 3/8\" to",
        "3/16\" (front) and from 3/8\" to 3/32\" (rear). Tissue tube: glue to motor stick (4 places).",
        "Filler: make from 1/8\" thick scrap hard balsa. Motor hook: make from 0.025\" dia. music wire.",
        "Bearing holder: make from 0.025\" or 0.032\" thk. 2024-T3 or 6061-T6 aluminum, 1/8\" dia. hole,",
        "centerline of bend, bend up 90 degrees. Wrap with thread and apply glue.",
        "5-1/2\" plastic prop, brass washers, Peck white nose bearing, 0.032\" dia. music wire.",
        "Suggested motor: 27\" loop of 0.075\" to 0.085\" wide Tan Super Sport.",
        "Empty weight balance point marked on the side view.",
        "Wingspan 17.93\", wing chord 4.47\", stab span 8.93\", stab chord 3.47\", overall length 17.81\",",
        "prop dia. 5.5\", minimum empty weight 7.5 grams. Complies with AMA event 227.",
    ]),
    ("P-18 CRUISER (designed and drawn by Bill Carney, AMA provisional rules 03/23/2016)", [
        "Shim L.E. 5/32\" [4 mm] during assembly (tip), 1/8\" [3.2 mm], 1/16\" [1.6 mm] inboard.",
        "Tips 3/32\" [2.4 mm], use template. Wing and rudder tip template, wing rib template,",
        "stab rib template.",
        "Wing ribs are 1/16\" [1.6 mm] x 3/32\" [2.4 mm]. Stab ribs, L.E., T.E. 1/16\" x 1/16\" [1.6 mm].",
        "No wing struts. Round L.E., T.E. and tip before assembling wing.",
        "1/4\" [6.4 mm] + incidence (wing). 1/8\" [3.24 mm] - incidence (stab).",
        "3/32\" [2.4 mm] round wing posts. Tissue tubes recommended but not required.",
        "Motor stick length 17.25\" [438 mm]; tapers from 1/8\" [3.2 mm] x 3/8\" [9.5 mm] to",
        "1/8\" [3.2 mm] x 3/16\" [4.4 mm].",
        "Stab outline 1/16\" [1.6 mm]. Rudder offset 1/4\" [6.4 mm].",
        "Dihedral 1 13/16\" [46 mm], 5/8\" [15.8 mm].",
        "Prototype consistently did 2:00 on 27\" [685 mm] loop of .085 [2 mm] tan SS.",
    ]),
]


# --------------------------------------------------------------------------
# Helpers for the trim details
# --------------------------------------------------------------------------
def prop_solid(mount_bb):
    """Commercial 6 inch two blade plastic prop on the thrust line, only for the
    pictures (not a model part): THRUST_DOWN / THRUST_LEFT as specified."""
    a, b = radians(m.THRUST_LEFT), radians(m.THRUST_DOWN)
    fwd = Vector(-cos(a) * cos(b), -sin(a) * cos(b), -sin(b))
    # 4 mm in front of the bearing's front end, on the thrust line
    piv = Vector(m.STICK_X0 - m.MOUNT_POCKET_BOTTOM + m.pukki.BEARING_Z0, 0, m.MOUNT_THRUST_Z)
    hub_c = piv + fwd * 4.0
    pl = Plane(origin=hub_c, x_dir=(0, 0, 1), z_dir=fwd)
    r = m.RULE_PROP_DIA / 2
    parts = [pl.location * Cylinder(3.5, 7)]
    blade = m.polygon_profile([(3, -5), (25, -9), (55, -8.5), (r - 2, -5), (r, -1), (r - 2, 3.5),
                               (55, 7), (25, 8), (3, 4.5)])
    for k in (0, 180):
        bl = extrude(blade, amount=0.5, both=True)
        bl = bl.rotate(Axis((0, 0, 0), (1, 0, 0)), 22)  # blade pitch
        bl = bl.rotate(Axis((0, 0, 0), (0, 0, 1)), k)
        parts.append(pl.location * bl)
    p = Compound(parts)
    p.label = "potkuri"
    return p, hub_c, fwd


def thrust_ud() -> str:
    d = m.THRUST_DOWN
    return "0° ylös/alas" if d == 0 else f"{fmt(abs(d))}° {'alas' if d > 0 else 'ylös'}"


def thrust_lr() -> str:
    l = m.THRUST_LEFT
    return "0° sivulle" if l == 0 else f"{fmt(abs(l))}° {'vasemmalle' if l > 0 else 'oikealle'}"


def thrust_text() -> str:
    return f"{thrust_ud()}, {thrust_lr()}"


def wing_pt(info, xl, y, zl):
    """Point in the wing frame (LE at x=0, rib end bottoms at z=0) -> model."""
    i = radians(m.WING_INCIDENCE)
    wz = m.wing_mount_z(info["chord"])
    return (m.WING_LE_X + xl * cos(i) + zl * sin(i), y, wz - xl * sin(i) + zl * cos(i))


def arc2(sh, c, r, a1, a2, text, size=TXT_S, text_r=None):
    """Arc on the sheet between sheet angles a1, a2 (degrees, y down) with arrows."""
    n = 30
    pts = [(c[0] + r * cos(radians(a1 + (a2 - a1) * k / n)), c[1] + r * sin(radians(a1 + (a2 - a1) * k / n)))
           for k in range(n + 1)]
    sh.poly(pts)
    for ang, sgn, p in ((a1, -1, pts[0]), (a2, 1, pts[-1])):
        t = radians(ang)
        s_ = 1 if a2 > a1 else -1
        sh.arrow(p, (-sin(t) * sgn * s_, cos(t) * sgn * s_), length=2.0, half=0.45)
    am = radians((a1 + a2) / 2)
    tr = text_r or r + 4
    sh.text(c[0] + tr * cos(am), c[1] + tr * sin(am) + 1, text, size=size, anchor="middle", bold=True)


def sheet_angle(p, q):
    return degrees(atan2(q[1] - p[1], q[0] - p[0]))


def box_note(sh, x, y, lines, size=TXT_S, w=None, bold_first=True):
    """Framed note block, top left at x, y; returns the bottom y."""
    w = w or max(len(s) for s in lines) * size * 0.56 + 4
    h = len(lines) * (size + 1.3) + 2.5
    sh.rect(x, y, w, h, w=0.35)
    for k, s in enumerate(lines):
        sh.text(x + 2, y + 2 + size + k * (size + 1.3), s, size=size, bold=(bold_first and k == 0))
    return y + h


def detail_title(sh, x, y, title, sub, size=TXT_L):
    sh.text(x, y, title, size=size, bold=True)
    if sub:
        sh.text(x, y + 5, sub, size=TXT_S)


# --------------------------------------------------------------------------
# 2024-2025 P-18 Online Indoor Postal Contest: classes (Limited!) and rule notes
# --------------------------------------------------------------------------
POSTAL_TEXTS = [  # (text, bold) — condensed from the contest page
    ("Classes: STANDARD P18 — no rubber restriction (AMA rules).", False),
    ("LIMITED P18 — a single rubber loop; before the loop is tied, the strip of rubber", True),
    ("cannot be longer than 40\" (1016 mm), i.e. a tied loop of about 19 3/4\" (502 mm).", True),
    ("(Keeps flight times reasonable: P18s can fly over 5 min on loops longer than 40\".)", False),
    ("Shopping bag = thin produce (veggie) bags, adhered with 3M 77 spray.", False),
    ("Unmodified prop = no sanding, scraping or re-pitching; own shaft and static balance", False),
    ("ballast allowed; the prop's own plastic bearing and wire shaft may be left out.", False),
    ("Printed plans must meet the chord and span limits.", False),
]


def check_layout(sh: Sheet, keep_out=()):
    """Texts must stay inside the drawing frame and must not overlap each other."""
    x0, y0, x1, y1 = FRAME
    out = [t for t in sh.texts if t[0] < x0 + 0.5 or t[2] > x1 - 0.5 or t[1] < y0 + 0.5 or t[3] > y1 - 0.5]
    over = []
    ts = sorted(sh.texts, key=lambda t: t[0])
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            if b[0] >= a[2]:
                break
            ix = min(a[2], b[2]) - max(a[0], b[0])
            iy = min(a[3], b[3]) - max(a[1], b[1])
            if ix > 0.6 and iy > 0.6:
                over.append((a[4], b[4]))
    print(f"Layout check: {len(sh.texts)} texts, {len(out)} outside the frame, {len(over)} overlapping pairs")
    for t in out[:10]:
        print(f"  OUTSIDE: {t[4]!r} at ({t[0]:.0f},{t[1]:.0f})-({t[2]:.0f},{t[3]:.0f})")
    for a, b in over[:15]:
        print(f"  OVERLAP: {a!r} / {b!r}")
    return not out and not over


def draw_profile(sh, prof, ox, oy, w=THICK, rot90=False):
    """A flat part's 2D profile at 1:1, profile origin at sheet (ox, oy), y up."""
    d = []
    for e in prof.edges():
        n = 1 if e.geom_type == GeomType.LINE else 8
        ps = [e.position_at(k / n) for k in range(n + 1)]
        if rot90:
            d.append("M" + " L".join(f"{ox + p.Y:.3f},{oy - p.X:.3f}" for p in ps))
        else:
            d.append("M" + " L".join(f"{ox + p.X:.3f},{oy - p.Y:.3f}" for p in ps))
    sh.path(" ".join(d), w=w)


# --------------------------------------------------------------------------
# The drawing
# --------------------------------------------------------------------------
def make(built=None):
    """Draw the sheet; `built` = (solids, flat, info) from the model's build(), or None to build."""
    solids, flat, info = built if built is not None else m.build()
    sh = Sheet()
    frame(sh)
    sh.texts.clear()  # the zone labels belong to the border, outside the frame on purpose
    allp = [s for g in solids.values() for s in g]
    W_ = solids["wing"]
    named = {s.label: s for s in allp}
    nums = {p.name: k for k, p in enumerate(flat, 1)}
    fp_by = {p.name: p for p in flat}
    mount = solids["hardware"][0]
    mb_ = mount.bounding_box()
    prop, hub_c, fwd = prop_solid(mb_)
    n_mount, n_hook, n_prop = (str(len(flat) + k) for k in (1, 2, 3))

    def bb(name):
        return named[name].bounding_box()

    tipL = min(s.bounding_box().min.Y for s in W_)
    tipR = max(s.bounding_box().max.Y for s in W_)
    chord = info["chord"]
    le = bb("wing_L_le_spar").min.X
    te = bb("wing_L_te_spar").max.X
    wz = m.wing_mount_z(chord)
    dih = info["dihedral"]
    w0, w1 = m.wedge_x(chord)
    hfw = m.WEDGE_MIN_H + (w1 - w0) * tan(radians(m.WEDGE_ANGLE))
    ss = solids["stab"]
    sb = Compound(ss).bounding_box()
    st_le = named["stab_le_spar_17"]
    zl = max(v.Z for v in st_le.vertices() if v.Y < -119)
    zr = max(v.Z for v in st_le.vertices() if v.Y > 119)
    zc = (zl + zr) / 2
    fin_parts = solids["fin"]
    fin_le = min(s.bounding_box().min.X for s in fin_parts)
    fin_top = max(s.bounding_box().max.Z for s in fin_parts)
    stab_le = sb.min.X

    def spar_tip(label, side):
        vs = named[label].vertices()
        ext = min(v.Y for v in vs) if side == "L" else max(v.Y for v in vs)
        v = max((v for v in vs if abs(v.Y - ext) < 0.6), key=lambda v: v.Z)
        return (v.X, v.Y, v.Z)

    # ================= COLUMN L: main views and parts, all 1:1 =================
    XL = 318.0
    # ---- L1 front view ----
    fv = View(allp, (-1, 0, 0), (0, 0, 1))
    fv.place(XL, 102)
    fv.draw(sh)
    x0, y0, x1, y1 = fv.sheet_bb()
    view_title(sh, XL, 22, "ETUKUVA", "1:1", "katsottuna edestä")
    a = fv.at((150, tipL, max(s.bounding_box().max.Z for s in W_ if s.bounding_box().min.Y < tipL + 3)))
    b = fv.at((150, tipR, max(s.bounding_box().max.Z for s in W_ if s.bounding_box().max.Y > tipR - 3)))
    c = fv.at((150, 0, 0))
    dim_h(sh, a[0], b[0], a[1], b[1], y0 - 11, f"{fmt(tipR - tipL)} (kärkiväli, projektio)")
    dim_h(sh, a[0], c[0], a[1], y0 - 2, y0 - 4, fmt(-tipL))
    dim_h(sh, c[0], b[0], y0 - 2, b[1], y0 - 4, fmt(tipR))
    sh.line((c[0], y0 - 13), (c[0], y1 + 4), w=0.18, dash="6 1 1 1")
    root = fv.at((105, 0, wz))
    angle_dim(sh, root, 70, 180, 180 + dih, f"V-kulma {fmt(dih, 2)}°")
    sh.line((root[0] - 75, root[1]), (root[0] - 2, root[1]), w=0.18, dash="6 1 1 1")
    rise = tipR * tan(radians(dih))
    rp = fv.at((150, tipR, wz + rise))
    dim_v(sh, root[1], rp[1], root[0] + 4, rp[0], min(a[0], b[0]) - 12, fmt(rise))
    leL, teL = spar_tip("wing_L_le_spar", "L"), spar_tip("wing_L_te_spar", "L")
    leR, teR = spar_tip("wing_R_le_spar", "R"), spar_tip("wing_R_te_spar", "R")
    pa, pb = fv.at(leL), fv.at(teL)
    dim_v(sh, pa[1], pb[1], pa[0], pb[0], max(pa[0], pb[0]) + 7, fmt(leL[2] - teL[2]))
    pa2, pb2 = fv.at(leR), fv.at(teR)
    dim_v(sh, pa2[1], pb2[1], pa2[0], pb2[0], min(pa2[0], pb2[0]) - 6, fmt(leR[2] - teR[2]))
    nb_x, nb_y = pb[0] - 150, y1 + 15
    box_note(sh, nb_x, nb_y, ["VASEMMAN SIIVEN JOHTOREUNA: WASH-IN 4 mm YLÖS",
                              f"Etu-/takareunan korkeusero kärjessä {fmt(leL[2] - teL[2])} = "
                              f"{fmt(leR[2] - teR[2])} (oikea) + 4 wash-in (ks. E).",
                              "Rakennetaan shimmeillä etureunan alla (taulukko keskellä)."], size=TXT_S, w=150)
    sh.line((nb_x + 150, nb_y + 4), (pa[0] + 1, pa[1] + 1))
    sh.arrow((pa[0] + 1, pa[1] + 1), (pa[0] + 1 - (nb_x + 150), pa[1] + 1 - (nb_y + 4)))
    lab_l = f"VASEN SIIPI — {fmt(info['spans']['L'])} rimaa pitkin"
    lab_r = f"OIKEA SIIPI — {fmt(info['spans']['R'])} rimaa pitkin"
    sh.text(min(a[0], b[0]) + 2, y1 + 9, lab_r if a[0] > b[0] else lab_l, size=TXT, bold=True)
    sh.text(min(a[0], b[0]) + 2, y1 + 15, "Korkeusvakaaja: vasen kärki +5, oikea −5 (ks. F)", size=TXT_S)
    ref_l, ref_r = fv.at((300, -122, zc)), fv.at((300, 122, zc))
    sh.line(ref_l, ref_r, w=0.18, dash="6 1 1 1")
    dim_v(sh, ref_l[1], fv.at((300, -120, zl))[1], ref_l[0], ref_l[0], ref_l[0] + 4, "+5")
    dim_v(sh, ref_r[1], fv.at((300, 120, zr))[1], ref_r[0], ref_r[0], ref_r[0] - 4, "−5")
    sh.text(max(a[0], b[0]) - 2, y1 + 9, lab_l if a[0] > b[0] else lab_r, size=TXT, bold=True, anchor="end")

    # ---- L2 wing plan ----
    pv = View(W_ + solids["wedge"], (0, 0, 1), (1, 0, 0))
    pv.place(XL, 270)
    pv.draw(sh)
    px0, py0, px1, py1 = pv.sheet_bb()
    view_title(sh, XL, py0 - 21, "SIIPI YLHÄÄLTÄ", "1:1", "etureuna alhaalla; rakennetaan tämän päällä")
    for side in ("L", "R"):
        ribs = sorted((s for s in W_ if re.match(rf"wing_{side}_rib", s.label)), key=lambda s: abs(s.bounding_box().center().Y))
        ys = [0.0] + [s.bounding_box().center().Y for s in ribs[1:]] + [tipL if side == "L" else tipR]
        te_x = bb(f"wing_{side}_te_spar").max.X
        xs = [pv.at((te_x, y, 0))[0] for y in ys]
        fs = [pv.at((te_x, y, 0))[1] for y in ys]
        order = sorted(range(len(xs)), key=lambda k: xs[k])
        dim_chain_h(sh, [xs[k] for k in order], [fs[k] for k in order], py0 - 7)
    cl, ct = pv.at((le, tipR, 0)), pv.at((te, tipR, 0))
    dim_v(sh, cl[1], ct[1], cl[0], ct[0], px0 - 6, fmt(te - le))
    leader(sh, pv.at((le + 1, tipR - 40, 0)), (px0 + 4, py1 + 12),
           [f"Etureunarima 4×2 kaarien kielekkeillä, kallistus {fmt(m.RIB_TAB_SLOPE)}° (yläpinnan mukaan)"], anchor="start")
    ws = bb("wing_wedge")
    leader(sh, pv.at((ws.min.X + 3, 0, 0)), (px1 - 4, py1 + 12), ["Kiila 4 mm balsa, 1 cm jännettä pidempi"], anchor="end")
    # every part numbered where it is built (small balloons)
    for s_ in W_:
        lab = s_.label
        c3 = s_.bounding_box().center()
        if "_rib" in lab:
            tip = pv.at((le + 22, c3.Y, 0))
            side = 1 if pv.at((le, 0, 0))[0] < tip[0] else -1
            balloon(sh, tip, (tip[0] + 6 * side, tip[1] - 6), str(nums[lab]), r=2.6)
        elif lab.endswith("_le_spar"):
            tip = pv.at((le + 1, c3.Y * 0.55, 0))
            balloon(sh, tip, (tip[0], tip[1] + 8), str(nums[lab]), r=2.6)
        elif lab.endswith("_te_spar"):
            tip = pv.at((te - 1, c3.Y * 0.55, 0))
            balloon(sh, tip, (tip[0], tip[1] + 8), str(nums[lab]), r=2.6)
        elif "center_spar" in lab:
            tip = pv.at((m.WING_LE_X + m.CENTER_SPAR_X, c3.Y, 0))
            balloon(sh, tip, (tip[0] + (8 if tip[0] > XL else -8), tip[1] - 7), str(nums[lab]), r=2.6)
    tip = pv.at((ws.min.X + 1.5, 0, 0)); balloon(sh, tip, (tip[0] + 9, tip[1] + 6), str(nums["wing_wedge"]), r=2.6)

    # ---- L3 side view ----
    sv = View(allp, (0, -1, 0), (0, 0, 1))
    sv.place_tl(52, 398)
    sv.draw(sh)
    sx0, sy0, sx1, sy1 = sv.sheet_bb()
    view_title(sh, sx0 + 150, sy0 - 32, "SIVUKUVA", "1:1", "katsottuna vasemmalta")
    nose = sv.at((m.STICK_X0, 0, 0)); tail = sv.at((m.TAIL_END_X, 0, 0))
    wl = sv.at((le, 0, wz))
    dim_h(sh, nose[0], wl[0], nose[1], wl[1], sy0 - 2, fmt(le - m.STICK_X0))
    pf = sv.at((fin_le, 0, fin_top))
    dim_h(sh, nose[0], pf[0], nose[1], pf[1], sy0 - 9, fmt(fin_le - m.STICK_X0))
    ps = sv.at((stab_le, 0, 2))
    dim_h(sh, nose[0], ps[0], nose[1], ps[1], sy0 - 16, fmt(stab_le - m.STICK_X0))
    ftp = sv.at((fin_le, 0, fin_top)); frt = sv.at((fin_le, 0, fin_top - m.RUDDER_HEIGHT))
    dim_v(sh, frt[1], ftp[1], frt[0], ftp[0], frt[0] - 6, fmt(m.RUDDER_HEIGHT))
    hf = sv.at((m.FRONT_HOOK_X, 0, m.MOUNT_THRUST_Z))
    sh.line((sv.at((mb_.min.X, 0, 0))[0] - 4, hf[1]), (tail[0] + 4, hf[1]), w=0.18, dash="8 1.2 1 1.2")
    sh.text(tail[0] + 5, hf[1] + 1, "vetoviiva 0°", size=TXT_S)
    for label, P, r in (("A", (145, 0, -2), 26), ("B", (12, 0, -10), 15)):
        c_ = sv.at(P)
        sh.add(f'<circle cx="{c_[0]:.2f}" cy="{c_[1]:.2f}" r="{r}" fill="none" stroke="#000" stroke-width="0.35" stroke-dasharray="4 1.5"/>')
        sh.text(c_[0] + r * 0.72 + 1, c_[1] - r * 0.72 - 1, label, size=6, bold=True)
    for name, P, off in (("wing_wedge", (115, 0, 1.5), (-14, -13)), ("fin_te", (fin_le + 30, 0, 25), (16, 6)),
                         ("stab_le_spar_17", (stab_le + 1, 0, 1), (-8, -12))):
        tip = sv.at(P)
        balloon(sh, tip, (tip[0] + off[0], tip[1] + off[1]), str(nums[name]))
    leader(sh, sv.at((ws.min.X + 2, 0, 5)), (sv.at((40, 0, 0))[0], sv.at((0, 0, 22))[1]),
           [f"Asetuskulma {fmt(m.WEDGE_ANGLE)}° (kiila 4 mm, ks. D)"], anchor="start")

    # ---- L4 fuselage side view 1:1 ----
    fus = [named["motor_stick"], mount, named["wing_wedge"], solids["hardware"][1]]
    rv = View(fus, (0, -1, 0), (0, 0, 1))
    rv.place_tl(52, sy1 + 30)
    rv.draw(sh)
    rx0, ry0, rx1, ry1 = rv.sheet_bb()
    sh.text(rx0, ry0 - 9, "RUNKO SIVULTA 1:1", size=TXT_L, bold=True)
    sh.text(rx0 + 62, ry0 - 9, "runkotikku 4 mm balsa, pukki, kiila, takakoukku; asemat tikun nokasta", size=TXT_S)
    nose = rv.at((m.STICK_X0, 0, 0)); tail = rv.at((m.TAIL_END_X, 0, 0))
    bot = rv.at((m.STICK_X0, 0, -m.STICK_H))
    yb = ry1 + 5
    dim_h(sh, nose[0], tail[0], bot[1], tail[1], yb + 12, f"{fmt(m.STICK_LEN)} runkotikku {fmt(m.STICK_H)}×{fmt(m.STICK_W)}")
    hf, hr = rv.at((m.FRONT_HOOK_X, 0, m.MOUNT_THRUST_Z)), rv.at((m.FRONT_HOOK_X + m.HOOK_TO_HOOK, 0, m.MOUNT_THRUST_Z))
    dim_h(sh, hf[0], hr[0], hf[1], hr[1], yb + 4, f"{fmt(m.HOOK_TO_HOOK)} koukkuväli")
    t0, t1 = rv.at((m.TAIL_END_X - m.STICK_TAPER_LEN, 0, -m.STICK_H)), rv.at((m.TAIL_END_X, 0, -m.STICK_H_TAIL))
    dim_h(sh, t0[0], t1[0], t0[1], t1[1], t0[1] + 4, fmt(m.STICK_TAPER_LEN))
    dim_v(sh, tail[1], t1[1], tail[0], t1[0], tail[0] + 7, fmt(m.STICK_H_TAIL))
    dim_v(sh, nose[1], bot[1], nose[0], bot[0], nose[0] - 14, fmt(m.STICK_H))
    for xs_, lab, dy_ in ((w0, "kiila", 4), (le, "siiven etureuna", 10), (stab_le, "korkeusvak.", 4),
                          (fin_le + m.RUDDER_FRAME_W / 2, "peräsimen akseli", 10)):
        p_ = rv.at((xs_, 0, 0))
        sh.line((p_[0], p_[1] - 1), (p_[0], ry0 - dy_ + 1), w=THIN)
        sh.arrow((p_[0], p_[1] - 0.5), (0, 1), length=2.0, half=0.45)
        sh.text(p_[0] + 1, ry0 - dy_ + 3, f"{lab} {fmt(xs_ - m.STICK_X0)}", size=2.2)
    tip = rv.at((200, 0, -4.5)); balloon(sh, tip, (tip[0] + 6, tip[1] + 14), str(nums["motor_stick"]))
    tip = rv.at((8, 0, -15)); balloon(sh, tip, (tip[0] - 10, tip[1] + 8), n_mount)
    tip = rv.at((w0 + 20, 0, 2)); balloon(sh, tip, (tip[0] + 14, tip[1] - 9), str(nums["wing_wedge"]))
    tip = rv.at((m.FRONT_HOOK_X + m.HOOK_TO_HOOK, 0, -14)); balloon(sh, tip, (tip[0] + 10, tip[1] + 6), n_hook)

    # ---- L5 stab plan 1:1 and rudder 1:1 ----
    stv = View(ss, (0, 0, 1), (1, 0, 0))
    stv.place_tl(52, yb + 40)
    stv.draw(sh)
    tx0, ty0, tx1, ty1 = stv.sheet_bb()
    view_title(sh, (tx0 + tx1) / 2, ty0 - 16, "KORKEUSVAKAAJA YLHÄÄLTÄ", "1:1", "tasainen, kaaret puskuliitoksin")
    a_, b_ = stv.at((sb.max.X, sb.min.Y, 0)), stv.at((sb.max.X, sb.max.Y, 0))
    dim_h(sh, a_[0], b_[0], a_[1], b_[1], ty0 - 4, fmt(sb.size.Y))
    c_ = stv.at((sb.min.X, sb.max.Y, 0))
    dim_v(sh, b_[1], c_[1], b_[0], c_[0], tx1 + 6, fmt(sb.size.X))
    ribs_s = sorted((s for s in ss if "rib" in s.label), key=lambda s: s.bounding_box().center().Y)
    ys = [sb.min.Y] + [s.bounding_box().center().Y for s in ribs_s] + [sb.max.Y]
    xs = sorted(stv.at((sb.min.X, y, 0))[0] for y in ys)
    dim_chain_h(sh, xs, [ty1] * len(xs), ty1 + 5)
    for s_ in ss:
        c3 = s_.bounding_box().center()
        if "rib" in s_.label:
            tip = stv.at((sb.min.X + 20, c3.Y, 0))
            balloon(sh, tip, (tip[0] + 6, tip[1] - 6), str(nums[s_.label]), r=2.6)
        else:
            tip = stv.at((c3.X, -60, 0))
            balloon(sh, tip, (tip[0] + 8, tip[1] + (7 if "le_" in s_.label else -7)), str(nums[s_.label]), r=2.6)
    # rudder flat 1:1 (frame of 4 strips, S joints)
    fx, fy = tx1 + 30, ty0 + 10
    sh.text(fx, ty0 - 16, "SIVUPERÄSIN 1:1", size=TXT_L, bold=True)
    sh.text(fx, ty0 - 10.5, "johtoreuna = kääntöakseli, S-liitokset", size=TXT_S)
    oy_f = fy + m.RUDDER_HEIGHT
    for p in flat:
        if p.name.startswith("fin_"):
            draw_profile(sh, p.profile, fx + 2, oy_f)
    dim_h(sh, fx + 2, fx + 2 + m.RUDDER_ROOT, oy_f, oy_f, oy_f + 6, fmt(m.RUDDER_ROOT))
    dim_h(sh, fx + 2, fx + 2 + m.RUDDER_TIP, oy_f - m.RUDDER_HEIGHT, oy_f - m.RUDDER_HEIGHT, oy_f - m.RUDDER_HEIGHT - 4,
          fmt(m.RUDDER_TIP))
    dim_v(sh, oy_f, oy_f - m.RUDDER_HEIGHT, fx + 2, fx + 2, fx - 3, fmt(m.RUDDER_HEIGHT))
    dim_v(sh, oy_f, oy_f + m.RUDDER_PIVOT, fx + 2, fx + 2, fx - 9, fmt(m.RUDDER_PIVOT))
    dim_h(sh, fx + 2, fx + 2 + m.RUDDER_FRAME_W, oy_f + m.RUDDER_PIVOT, oy_f + m.RUDDER_PIVOT, oy_f + m.RUDDER_PIVOT + 5,
          fmt(m.RUDDER_FRAME_W))
    for name, (px_, py_), off in (("fin_te", (40, 30), (12, 0)), ("fin_root", (25, 2), (0, 12)),
                                  ("fin_top", (15, m.RUDDER_HEIGHT - 2), (0, -11)), ("fin_le", (2, 30), (-12, 0))):
        tip = (fx + 2 + px_, oy_f - py_)
        balloon(sh, tip, (tip[0] + off[0], tip[1] + off[1]), str(nums[name]), r=2.8)

    # ---- shim table (left wing wash-in), right of the rudder ----
    shx, shy = fx + m.RUDDER_ROOT + 30, ty0 - 16
    sh.text(shx, shy, "SHIMMIT — VASEMMAN SIIVEN WASH-IN 4 mm", size=TXT, bold=True)
    sh.text(shx, shy + 4.5, "Rakenna jättöreuna alustaa vasten, shimmi etureunan", size=2.2)
    sh.text(shx, shy + 8, "alle kunkin kaaren kohdalle (johtoreuna nousee). Oikea siipi suorana.", size=2.2)
    _, st = m.wing_spar_profile(m.WING_HALVES["L"][1], radians(dih))
    sugg = {0.8: "0,8 vaneri / 1/32\"", 1.6: "1/16\" balsa", 2.4: "3/32\" balsa", 3.2: "1/8\" balsa", 4.0: "5/32\" balsa"}
    srows = []
    for i, s_ in enumerate(st):
        rise = m.WASH_IN_LEFT * s_ / st[-1] if i else 0.0
        name = next(p.name for p in flat if p.name.startswith(f"wing_L_rib{i}_"))
        key = min(sugg, key=lambda v: abs(v - rise)) if rise > 0.3 else None
        srows.append([str(nums[name]), ["Tyvikaari", "Täysikaari"][i] if i < 2 else "Siipikaari",
                      fmt(s_), fmt(rise, 1) if i else "0", sugg[key] if key else "—"])
    table(sh, shx, shy + 11, [11, 24, 27, 20, 46], ["OSA", "KAARI", "KESKELTÄ", "SHIMMI", "ESIM. LEVY"],
          srows, row_h=4.2, size=2.2)
    shim_bottom = shy + 11 + 4.2 * (len(srows) + 1)

    # ---- L6 bottom left corner: three-view, as big as the corner allows ----
    l_top = max(ty1 + 18, oy_f + m.RUDDER_PIVOT + 16)
    tv_f = View(allp, (-1, 0, 0), (0, 0, 1))  # from the front
    tv_s = View(allp, (0, -1, 0), (0, 0, 1))  # from the left
    tv_t = View(allp, (0, 0, 1), (0, 1, 0))   # from above, nose left like the side view
    # front and left view side by side at the bottom left; the tall top view at the
    # right end of the column, under the shim table, where there is more height
    row_gap, l_right = 14.0, 612.0 - 8  # column M starts at x 612
    t_top = shim_bottom + 14
    w_model = sum(v_.bb[2] - v_.bb[0] for v_ in (tv_f, tv_s, tv_t))
    h_fs = max(v_.bb[3] - v_.bb[1] for v_ in (tv_f, tv_s))
    h_t = tv_t.bb[3] - tv_t.bb[1]
    avail_h = FRAME[3] - 18 - (l_top + 14) - 10
    avail_t = FRAME[3] - 18 - (t_top + 6) - 12
    den = next(n for n in (2, 3, 4, 5, 6, 8, 10, 15, 20)
               if h_fs / n <= avail_h and h_t / n <= avail_t and w_model / n + 2 * row_gap <= l_right - 34)
    for v_ in (tv_f, tv_s, tv_t):
        v_.scale = 1 / den
    sh.text(30, l_top, f"KOLMITAHOKUVA 1:{den}", size=TXT_L, bold=True)
    sh.text(30, l_top + 5, "edestä, vasemmalta ja ylhäältä (nokka vasemmalla)", size=TXT_S)
    tv_f.place_tl(34, l_top + 14)
    f_bb = tv_f.sheet_bb()
    tv_s.place_tl(f_bb[2] + row_gap, l_top + 14)
    tv_t.place_tl(max(tv_s.sheet_bb()[2] + row_gap, l_right - (tv_t.bb[2] - tv_t.bb[0]) / den), t_top + 6)
    for v_, lab in ((tv_f, "edestä"), (tv_s, "vasemmalta"), (tv_t, "ylhäältä")):
        v_.draw(sh, w=0.3)
        b_ = v_.sheet_bb()
        sh.text((b_[0] + b_[2]) / 2, b_[3] + 4, lab, size=2.2, anchor="middle")
    s_bb, t_bb = tv_s.sheet_bb(), tv_t.sheet_bb()
    dim_h(sh, f_bb[0], f_bb[2], f_bb[3], f_bb[3], f_bb[3] + 9, fmt(tipR - tipL))
    dim_h(sh, t_bb[0], t_bb[2], t_bb[3], t_bb[3], t_bb[3] + 9, fmt(m.TAIL_END_X - mb_.min.X))
    dim_h(sh, s_bb[0], s_bb[2], s_bb[3], s_bb[3], s_bb[3] + 9, fmt(m.TAIL_END_X - mb_.min.X))
    tv_right = max(f_bb[2], s_bb[2], t_bb[2])

    # F (stab tilt) is drawn in column M under H
    vf = View(crop(allp, (m.TAIL_END_X - 80, -130, -12), (m.TAIL_END_X + 6, 130, 70)), (1, -0.38, 0.32), (0, 0, 1), scale=3.0, hidden=True)

    # ================= COLUMN M: 3D views, stacked with even gaps =================
    MX, MW = 612.0, 240.0
    iso_all = View(allp + [prop], (-1, -1.25, 0.75), (0, 0, 1), scale=1.0, hidden=True).fit(MW - 8)
    reg = crop([s for s in allp if s.label != "pukki"], (88, -26, -11), (206, 6, 16))
    vd = View(reg, (-0.32, -1, 0.3), (0, 0, 1), scale=4.0, hidden=True).fit(MW - 12)
    # E (wash-in) goes to column R above the parts list, with the four outer left ribs
    ve = View(crop(W_, (95, -252, -10), (200, -88, 70)), (1, -0.8, 0.55), (0, 0, 1), scale=4.0, hidden=True)
    vg = View(crop(allp, (fin_le - 8, -9, -20), (fin_le + 58, 9, 66)), (-0.55, -1.0, 0.75), (0, 0, 1), scale=4.0, hidden=True).fit(MW - 70, 165)
    nose_sh = crop([mount, named["motor_stick"], prop], (-14, -24, -40), (30, 24, 6))
    ht = View(nose_sh, (0, 0, 1), (0, 1, 0), scale=1.7)
    hs = View(nose_sh, (0, -1, 0), (0, 0, 1), scale=1.0)
    avail = FRAME[3] - 6 - 18
    others = [iso_all.size[1] + 14, vd.size[1] + 26, vg.size[1] + 26, max(ht.size[1], hs.size[1]) + 24]
    vf.fit(MW - 24, avail - sum(others) - 4 * 10 - 30)
    blocks = others + [vf.size[1] + 30]
    gap = max(8.0, min(40.0, (avail - sum(blocks)) / (len(blocks) - 1)))
    if sum(blocks) + gap * (len(blocks) - 1) > avail + 1:
        print(f"WARNING: column M needs {sum(blocks) + gap * (len(blocks) - 1):.0f} mm, has {avail:.0f}")
    y_ = 20.0

    detail_title(sh, MX, y_, f"{MODEL_NAME.upper()} — 3D", "6\" muovipotkuri (havainnekuva); katkoviiva = piilossa oleva särmä")
    iso_all.place_tl(MX + 4, y_ + 10)
    iso_all.draw(sh, w=0.35)
    tip = iso_all.at(hub_c + Vector(0, 0, 45)); balloon(sh, tip, (tip[0] - 12, tip[1] - 4), n_prop, arrow=True)
    y_ += blocks[0] + gap

    detail_title(sh, MX, y_, "D — SIIVEN ASETUSKULMA 2°", "siiven jänne 2° runkoon nähden; kiila 4 mm balsa")
    vd.place_tl(MX + 6, y_ + 14)
    vd.draw(sh, w=0.35)
    d0 = vd.sheet_bb()
    yy_ = -2.0
    s1, s2 = vd.at((88, yy_, 0)), vd.at((206, yy_, 0))
    sh.line(s1, s2, w=0.3, dash="8 1.2 1 1.2")
    sh.text(s2[0] - 2, s2[1] + 5, "rungon yläpinta", size=TXT_S, anchor="end")
    c1, c2 = vd.at(wing_pt(info, -12, yy_, 0)), vd.at(wing_pt(info, chord + 18, yy_, 0))
    sh.line(c1, c2, w=0.5)
    sh.text(c1[0] + 1, c1[1] - 3, "siiven jänne", size=TXT_S, anchor="start")
    lep = vd.at(wing_pt(info, 0, yy_, 0))
    par = vd.at(Vector(wing_pt(info, 0, yy_, 0)) + Vector(chord + 18, 0, 0))
    sh.line(lep, par, w=0.3, dash="4 1.5")
    arc2(sh, lep, 0.85 * hypot(par[0] - lep[0], par[1] - lep[1]), sheet_angle(lep, par), sheet_angle(lep, c2), "2°",
         size=TXT_L, text_r=0.85 * hypot(par[0] - lep[0], par[1] - lep[1]) + 7)
    low = d0[3]
    for name, P, off in (("wing_L_leg_front_25", (106, -3, -5), (-14, 12)), ("wing_L_leg_rear_35", (183, -3, -4), (12, 12)),
                         ("wing_wedge", (150, -2, 3.5), (0, 16)), ("motor_stick", (120, -2, -5), (-30, 6))):
        tip = vd.at(P)
        balloon(sh, tip, (tip[0] + off[0], tip[1] + off[1]), str(nums[name]), arrow=True)
        low = max(low, tip[1] + off[1] + 4)  # balloon bottom
    sh.text(MX, low + 8, f"2° = kiilan nousu {fmt(hfw - m.WEDGE_MIN_H)} mm / {fmt(w1 - w0)} mm "
            f"(etupää {fmt(hfw)}, takapää {fmt(m.WEDGE_MIN_H)} mm)", size=TXT_S)
    y_ += blocks[1] + gap


    detail_title(sh, MX, y_, "G — SIVUPERÄSIN 2° VASEMMALLE", "jättöreuna vasemmalle: alhaalla 1,7 mm, ylhäällä 1,0 mm")
    vg.place_tl(MX + (MW - vg.size[0]) / 2, y_ + 14)
    vg.draw(sh, w=0.35)
    g0 = vg.sheet_bb()
    yh = m.RUDDER_SIDE * ((m.STICK_W + m.SHEET_T) / 2 + m.RUDDER_HINGE_GAP)
    xh = m.TAIL_END_X - m.RUDDER_FORWARD - m.RUDDER_ROOT + m.RUDDER_FRAME_W / 2
    zr_ = min(s.bounding_box().min.Z for s in fin_parts if s.label == "fin_root")

    def turned(xlen, z, ang):
        return (xh + xlen * cos(radians(ang)), yh - xlen * sin(radians(ang)), z)
    for xlen, z, lab, side in ((m.RUDDER_ROOT - m.RUDDER_FRAME_W / 2, zr_, "1,7", 1),
                               (m.RUDDER_TIP - m.RUDDER_FRAME_W / 2, fin_top, "1,0", -1)):
        sh.line(vg.at(turned(-6, z, 0)), vg.at(turned(xlen + 8, z, 0)), w=0.3, dash="6 1 1 1")
        dim(sh, vg.at(turned(xlen, z, 0)), vg.at(turned(xlen, z, m.RUDDER_TURN)), 9 * side, f"{lab} mm", size=TXT)
    sh.text(MX, g0[3] + 8, "pistekatkoviiva = rungon suuntainen (peräsin suorassa)", size=TXT_S)
    y_ += blocks[2] + gap

    detail_title(sh, MX, y_, "H — POTKURIN AKSELI",
                 f"{thrust_text()}; pukin laakeriputki tehty tähän kulmaan (pukki.txt)")
    ht.place_tl(MX + 58, y_ + 14)
    ht.draw(sh, w=0.3)
    h0 = ht.sheet_bb()
    sh.line(ht.at((-12, 0, 0)), ht.at((32, 0, 0)), w=0.25, dash="8 1.2 1 1.2")
    tl1, tl2 = ht.at(hub_c + fwd * 30), ht.at(hub_c - fwd * 30)
    sh.line(tl1, tl2, w=0.45)
    hc = ht.at(hub_c)
    fwd_ax = ht.at(hub_c + Vector(-30, 0, 0))
    sh.line(hc, fwd_ax, w=0.25, dash="3 1.5")
    arc2(sh, hc, 48, sheet_angle(hc, fwd_ax), sheet_angle(hc, tl1), f"{fmt(abs(m.THRUST_LEFT))}°", size=TXT, text_r=54)
    sh.text((h0[0] + h0[2]) / 2, h0[3] + 5, f"ylhäältä — {thrust_lr()}", size=TXT_S, anchor="middle")
    hs.place_tl(h0[2] + 12, y_ + 14)
    hs.draw(sh, w=0.3)
    s0_ = hs.sheet_bb()
    q1, q2 = hs.at(hub_c + fwd * 12), hs.at(hub_c - fwd * 30)
    sh.line(q1, q2, w=0.45)
    sh.text(q2[0] + 2, q2[1] - 1.5, f"{fmt(abs(m.THRUST_DOWN))}°", size=TXT, bold=True)
    sh.text((s0_[0] + s0_[2]) / 2, s0_[3] + 5, f"sivulta — {thrust_ud()}", size=TXT_S, anchor="middle")
    y_ += blocks[3] + gap

    detail_title(sh, MX, y_, "F — KORKEUSVAKAAJAN TILTTI ±5 mm (3D)",
                 "oikea kärki 5 alempana, vasen 5 ylempänä; pistekatkoviiva = suora rima rungon päällä")
    vf.place_tl(MX + (MW - vf.size[0]) / 2, y_ + 18)
    vf.draw(sh, w=0.4)
    rl, rr = vf.at((sb.max.X, -125, zc)), vf.at((sb.max.X, 125, zc))
    sh.line(rl, rr, w=0.3, dash="8 1.2 1 1.2")
    tl_ = max((v for v in st_le.vertices() if v.Y < -119), key=lambda v: v.Z)
    tr_ = max((v for v in st_le.vertices() if v.Y > 119), key=lambda v: v.Z)
    dim(sh, vf.at((tl_.X, tl_.Y, zc)), vf.at((tl_.X, tl_.Y, tl_.Z)), 10, "+5 mm (vasen)", size=TXT_L)
    dim(sh, vf.at((tr_.X, tr_.Y, zc)), vf.at((tr_.X, tr_.Y, tr_.Z)), -10, "−5 mm (oikea)", size=TXT_L)
    for s_ in ss:
        if "le_spar" in s_.label:
            tip = vf.at((s_.bounding_box().center().X, 60, zc))
            balloon(sh, tip, (tip[0] + 10, tip[1] + 14), str(nums[s_.label]), arrow=True)
    for v_ in (iso_all, vd, vg, ht, hs, vf):
        if v_.sheet_bb()[2] > MX + MW + 2:
            print(f"WARNING: a column M view runs to x {v_.sheet_bb()[2]:.0f}")

    # ================= COLUMN R: saddle (big), mount, data, rules, texts, parts, title =================
    RX0, RX1 = 862.0, FRAME[2] - 4
    RW = RX1 - RX0
    ay = 20
    detail_title(sh, RX0, ay, "DETALJI A — SIIPISATULA (3D)", "nuoli osoittaa osaan, numero = osaluettelo / laserkaiverrus")
    sad = crop([s for s in allp if s.label != "pukki"], (95, -17, -10), (195, 17, 16))
    iso = View(sad, (-1, -1.2, 0.9), (0, 0, 1), scale=1.75 * 1.6, hidden=True).fit(RW - 70)
    iso.place_tl(RX0 + 36, ay + 18)
    iso.draw(sh, w=0.4)
    ix0, iy0, ix1, iy1 = iso.sheet_bb()
    root_l = next(n for n in nums if n.startswith("wing_L_rib0_"))
    root_r = next(n for n in nums if n.startswith("wing_R_rib0_"))
    for name, P, off in (("wing_L_leg_front_25", (106, -3.5, -6), (-26, 12)), ("wing_L_leg_rear_35", (183, -3.5, -5), (18, 18)),
                         ("wing_wedge", (125, 0, 3), (-30, -6)), ("motor_stick", (140, -2, -6), (-8, 26)),
                         (root_l, wing_pt(info, 22, -2.0, 4.5), (-8, -30)), (root_r, wing_pt(info, 62, 1.0, 5.6), (24, -26)),
                         ("wing_L_le_spar", (106, -14, 7), (-30, -14)), ("wing_L_te_spar", (184, -14, 6), (26, -12))):
        tip = iso.at(P)
        balloon(sh, tip, (tip[0] + off[0], tip[1] + off[1]), str(nums[name]), r=4.2, arrow=True)
    by = iy1 + 24
    detail_title(sh, RX0, by, "DETALJI B — MOOTTORIPUKKI",
                 f"3D-tulostettu (step/pukki.stl); tasku 4×{fmt(m.STICK_H + m.PUKKI['taskun_vara'])}, syvyys 10; laakeri ⌀2 / reikä ⌀{fmt(m.PUKKI['laakerireika'])}")
    msh = crop([mount, named["motor_stick"]], (0, -5, -22), (26, 5, 3))
    bs = View(msh, (0, -1, 0), (0, 0, 1), scale=3.2, hidden=True)
    bs.place_tl(RX0 + 16, by + 14)
    bs.draw(sh, w=0.4)
    bx0, by0, bx1, by1 = bs.sheet_bb()
    sh.text((bx0 + bx1) / 2, by1 + 12, "SIVUKUVA 3,2:1", size=TXT_S, anchor="middle")
    pt_, pbm = bs.at((m.STICK_X0, 0, mb_.max.Z)), bs.at((m.STICK_X0, 0, mb_.min.Z))
    dim_v(sh, pt_[1], pbm[1], bx0, bx0, bx0 - 5, fmt(mb_.size.Z))
    pf_, pb2_ = bs.at((mb_.min.X, 0, mb_.min.Z)), bs.at((mb_.max.X, 0, mb_.min.Z))
    dim_h(sh, pf_[0], pb2_[0], pf_[1], pb2_[1], by1 + 6, fmt(mb_.size.X))
    stp = bs.at((mb_.max.X, 0, 0))
    dim_v(sh, stp[1], bs.at((mb_.max.X, 0, m.MOUNT_THRUST_Z))[1], stp[0], stp[0], bx1 + 5, fmt(-m.MOUNT_THRUST_Z))
    bi = View([mount] + crop([named["motor_stick"]], (10, -5, -12), (40, 5, 2)), (-1, -1.1, 0.8), (0, 0, 1),
              scale=3.0, hidden=True).fit(RX1 - bx1 - 50)
    bi.place_tl(bx1 + 34, by + 13)
    bi.draw(sh, w=0.35)
    jx0, jy0, jx1, jy1 = bi.sheet_bb()
    tip = bi.at((14, 0, -3)); balloon(sh, tip, (tip[0] + 14, tip[1] - 10), n_mount, arrow=True)
    tip = bi.at((32, 0, -4)); balloon(sh, tip, (tip[0] + 12, tip[1] + 10), str(nums["motor_stick"]), arrow=True)

    # technical data
    ty = max(by1 + 14, jy1) + 14
    wing_area = (tipR - tipL) * (te - le) / 1e4
    stab_area = sb.size.Y * sb.size.X / 1e4
    data = [
        ["Kärkiväli rimaa pitkin / projektio", f"{fmt(info['spans']['L'] + info['spans']['R'])} (V 245 + O 235) / {fmt(tipR - tipL)} mm"],
        ["Siiven jänne / pinta-ala", f"{fmt(chord)} mm / {fmt(wing_area, 2)} dm²"],
        ["V-kulma / asetuskulma", f"{fmt(dih, 2)}° / {fmt(m.WEDGE_ANGLE)}° (D)"],
        ["Reunarimat", f"4×2, kallistus {fmt(m.RIB_TAB_SLOPE)}° yläpinnan mukaan"],
        ["Wash-in", f"vasen siipi, johtoreuna kärjessä {fmt(m.WASH_IN_LEFT)} mm ylempänä (E)"],
        ["Korkeusvakaaja", f"{fmt(sb.size.Y)}×{fmt(sb.size.X)} mm, {fmt(stab_area, 2)} dm², tiltti ±{fmt(m.STAB_TILT)} mm (F)"],
        ["Sivuperäsin", f"{fmt(m.RUDDER_ROOT)}/{fmt(m.RUDDER_TIP)}×{fmt(m.RUDDER_HEIGHT)} mm, {fmt(m.RUDDER_TURN)}° vasemmalle (G)"],
        ["Vetoviiva", f"{thrust_text()} (H, pukki.txt)"],
        ["Pituus ilman potkuria / koukkuväli", f"{fmt(m.TAIL_END_X - mb_.min.X)} mm / {fmt(m.HOOK_TO_HOOK)} mm"],
        ["Moottori, Limited P18", "1 lenkki, nauha ennen solmimista ≤ 1016 mm (40\")"],
    ]
    tb_bottom = table(sh, RX0, ty, [64, RW - 64], ["TEKNISET TIEDOT", ""], data, row_h=4.3, size=2.4)

    ny = tb_bottom + 9
    sh.text(RX0, ny, "HUOMAUTUKSET", size=TXT, bold=True)
    notes = [
        "1. Mitat mm. Pääkuvat 1:1: tulosta A0 100 %, tarkista viivaimella →",
        "2. Osanumerot = osaluettelo ja laserkaiverrus (laser/osat2mm*, osat4mm*).",
        "3. Balsan syy osan pituussuuntaan. Siipikaariin ei kaiverreta numeroa.",
        "4. 3D-kuvat havainnekuvia; piilossa olevat särmät katkoviivalla.",
        "5. POTKURIN LAAKERI: 2 lasihelmeä + vähintään 3 mylar-prikkaa; voitele teflonöljyllä.",
    ]
    for k, s_ in enumerate(notes):
        sh.text(RX0, ny + 4.8 + k * 3.8, s_, size=2.4, bold=s_.startswith("5."))
    cb_y = ny + 4.8 + len(notes) * 3.8 + 3
    sh.line((RX0, cb_y), (RX0 + 100, cb_y), w=0.5)
    for kk in range(11):
        sh.line((RX0 + kk * 10, cb_y), (RX0 + kk * 10, cb_y - (3 if kk % 5 == 0 else 1.6)), w=THIN)
    sh.text(RX0 + 103, cb_y + 1, "100 mm tarkistusmitta", size=2.2)

    ly = cb_y + 10
    sh.text(RX0, ly, "P-18 STANDARD / LIMITED (2024–2025 P-18 Online Indoor Postal Contest, AMA #227)", size=2.8, bold=True)
    for k, (ln, bold_) in enumerate(POSTAL_TEXTS):
        sh.text(RX0, ly + 4.6 + k * 3.0, ln, size=2.3, bold=bold_)
    lim_bottom = ly + 4.6 + len(POSTAL_TEXTS) * 3.0

    prow = parts_list(flat)
    tb_w = RW + 4
    title_top = title_block(sh, FRAME[2] - tb_w, FRAME[3], tb_w)
    rev_top = revision_block(sh, FRAME[2] - tb_w, title_top, tb_w)
    row_h = 3.8
    pl_top = rev_top - row_h * (len(prow) + 1)
    table(sh, FRAME[2] - tb_w, pl_top, [24, 82, 10, 40, tb_w - 156], ["OSA", "NIMITYS", "KPL", "MITAT mm", "AINE"],
          prow[::-1], row_h=row_h, size=2.25)
    sh.text(FRAME[2] - tb_w, pl_top - 2, "OSALUETTELO", size=TXT, bold=True)

    uy = lim_bottom + 8
    sh.text(RX0, uy, "AMERIKKALAISTEN P-18-PIIRUSTUSTEN TIEDOT (bigsmash, p-18_pursuit, p18_cruiser)", size=2.6, bold=True)
    lines = []
    for head, ls in US_TEXTS:
        lines.append(("H", head if len(head) < 62 else head[:head.index("(")].strip()))
        lines += [("T", l) for l in ls]
    ncol = 3
    col_w = RW / ncol
    per_col = -(-len(lines) // ncol)
    avail = pl_top - 10 - (uy + 3)
    lh = min(2.6, avail / per_col)
    fs_ = min(2.0, lh * 0.8, col_w / (0.57 * max(len(l) for _, l in lines)))
    if lh < 1.6:
        print(f"WARNING: US texts are cramped (line height {lh:.2f} mm)")
    for k, (kind, ln) in enumerate(lines):
        col, row = divmod(k, per_col)
        sh.text(RX0 + col * col_w, uy + 3 + row * lh + 1.6, ln, size=fs_ + (0.1 if kind == "H" else 0), bold=(kind == "H"))
    us_bottom = uy + 3 + per_col * lh + 2

    # ---- E: wash-in of the left wing, four outer ribs, in the free space above the parts list ----
    ey = us_bottom + 9
    e_room = pl_top - 8 - (ey + 16) - 14  # title above, rib labels below
    if e_room < 60:
        print(f"WARNING: detail E has only {e_room:.0f} mm height")
    ve.fit(RW - 70, e_room)
    detail_title(sh, RX0, ey, f"E — WASH-IN, VASEN SIIPI {fmt(m.WASH_IN_LEFT)} mm",
                 "katsottuna takaa vasemmalta (lentäjän suunnasta); johtoreuna nousee kärkeä kohti tasaisesti, "
                 f"kärjessä {fmt(m.WASH_IN_LEFT)} mm; jättöreuna suorana")
    ve.place_tl(RX0 + 66, ey + 16)
    ve.draw(sh, w=0.35)
    e0 = ve.sheet_bb()
    lev = named["wing_L_le_spar"].vertices()
    tip_v = max((v for v in lev if v.Y < tipL + 0.6), key=lambda v: v.Z - v.X)  # LE tip, top front corner
    mid_v = max((v for v in lev if abs(v.Y + 100) < 6), key=lambda v: v.Z - v.X - abs(v.Y + 100))
    ph_tip = Vector(tip_v.X, tip_v.Y, tip_v.Z - m.WASH_IN_LEFT)  # where the LE would be without wash-in
    ph_mid = Vector(mid_v.X, mid_v.Y, mid_v.Z - m.WASH_IN_LEFT * abs(mid_v.Y) / abs(tip_v.Y))
    sh.line(ve.at(ph_mid), ve.at(ph_tip), w=0.4, dash="3 1.5")
    a_lo, a_hi = ve.at(ph_tip), ve.at((tip_v.X, tip_v.Y, tip_v.Z))
    dim(sh, a_lo, a_hi, 7, f"{fmt(m.WASH_IN_LEFT)} mm", size=TXT_L)
    # big upward arrow beside the LE tip: the LE goes up
    ax_ = a_lo[0] - 13
    sh.line((ax_, a_lo[1] + 10), (ax_, a_hi[1]), w=0.6)
    sh.arrow((ax_, a_hi[1]), (0, -1), length=4, half=1.4)
    sh.text(ax_ - 3, a_lo[1] + 9, f"JOHTOREUNA YLÖS {fmt(m.WASH_IN_LEFT)} mm", size=TXT, bold=True, anchor="end")
    kt = ve.at((tip_v.X, tip_v.Y, tip_v.Z))
    sh.text(kt[0] + 4, kt[1] - 9, "VASEN KÄRKI", size=TXT, bold=True, anchor="start")
    ri = ve.at((150, -92, 40))
    sh.text(ri[0], ri[1] - 2, "runkoa kohti →" if ri[0] > kt[0] else "← runkoa kohti", size=TXT_S,
            anchor="end" if ri[0] > kt[0] else "start")
    # under every rib: how much its LE is raised (linear from the root to WASH_IN_LEFT at the tip)
    _, st_l = m.wing_spar_profile(m.WING_HALVES["L"][1], radians(dih))
    for i, s_ in enumerate(st_l):
        rib = next((x for x in W_ if x.label.startswith(f"wing_L_rib{i}_")), None)
        if i < 2 or rib is None:
            continue
        rv_ = rib.vertices()
        te_end = max(rv_, key=lambda v: v.X - 0.01 * v.Z)  # TE end, bottom
        p_ = ve.at(te_end)
        if not (e0[0] - 1 <= p_[0] <= e0[2] + 1):
            continue
        rise = m.WASH_IN_LEFT * s_ / st_l[-1]
        sh.text(p_[0], p_[1] + 7, f"osa {nums[rib.label]}", size=TXT_S, bold=True, anchor="middle")
        sh.text(p_[0], p_[1] + 10.5, f"johtoreuna +{fmt(rise)} mm", size=TXT_S, anchor="middle")
    sh.text(RX0, e0[3] + 14, "lyhyt katkoviiva = johtoreuna ilman wash-iniä; nostot = shimmit johtoreunan alla "
            "(taulukko SHIMMIT)", size=TXT_S)

    check_layout(sh)
    OUT_DIR.mkdir(exist_ok=True)
    for old in list(OUT_DIR.glob("HYT-P18-001_*")):
        old.unlink()
    base = OUT_DIR / f"{DRAWING_NO}_{REVISION}"
    svg = sh.svg()
    base.with_suffix(".svg").write_text(svg)
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(base.with_suffix(".pdf")))
    return base.with_suffix(".svg"), base.with_suffix(".pdf")


if __name__ == "__main__":
    for f in make():
        print(f)
