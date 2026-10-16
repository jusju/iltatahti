"""
Iltatähti P-18 — P-18 style rubber powered indoor model, built mainly from the
laser parts of the kit sheet hyttynen4-indoor-ff-supply-5cm-49cm.dxf.

P-18 rules (AMA event 227) for reference, checked at the end of a run:
  - wing chord <= 4.5"  (114.3 mm), projected span <= 18" (457.2 mm)
  - stab span  <= 9"    (228.6 mm), chord <= 3.5" (88.9 mm)
  - overall length incl. propeller <= 18" (457.2 mm)
  - commercial plastic prop, nominal max 6" diameter
  - hook to hook <= 10" (254 mm)
  - min weight 7.5 g without rubber
The wing (480 mm along the spars) and stab (240 mm) follow the kit parts and are
larger than P-18 allows, so those two checks fail on purpose.

Parts from the DXF (numbers = iltatahti_dxf_osat.svg):
  wing   - root ribs 22, 27 and full ribs 8, 12 (center spar notch),
           other ribs from 2, 5, 30 ... 43
  stab   - LE / TE spars the size of 17, 23 (240 x 3.1 mm), flat
  mount  - saddle legs 25, 26 (front) and 35, 36 (rear) along the airflow, against
           the stick sides next to the root ribs. Their notch has the same shape as
           the rib end tab, so the LE / TE spar is glued into it like into a rib.
           Lengthened down to the stick bottom
Generated here, in the style of the DXF parts:
  wing spars - like DXF spar 9 (width, notch depth), lying on the sloped rib end
               tabs so they follow the curved upper surface, notches towards the ribs; left 245 mm / right 235 mm (left 1 cm
               longer, 480 mm in all), 6 rib notches 2 mm wide for the 2 mm ribs;
               the root bevel of DXF spar 9 gives the dihedral
  center spars - V-dihedral support from the centerline to the full ribs, in the
               rib notches flush with the rib tops
  stab ribs  - straight strips butt-jointed between the flat LE / TE spars
  fin        - turning rudder on the stick side: LE vertical, 20 mm longer at the
               bottom (hinge), chord 50 mm at the root, 30 mm at the top, 4 strips
  fuselage   - motor stick 7 x 497 mm (STICK_H from pukki.txt; 50 cm strip less 3 mm), rear part tapers to 4 mm
  wedge      - incidence wedge under the wing
3D printed: motor mount pukki.py (parametric, angles in pukki.txt) on the stick
nose, prop shaft bearing below the stick. The prop (commercial 6 inch plastic) is not modelled.

Coordinates: X aft (nose = 0), Y towards the right wing (pilot's right, +), Z up.

Every flat balsa part is a 2D profile + sheet thickness, so the laser SVGs are
made from exactly the parts in the 3D model.

Normally run sync_all.py: it updates only what a change needs, and also reads
part outlines edited in the laser SVGs back into the model (overrides/).
Run:  .venv/bin/python sync_all.py [--watch]       sync model / laser / drawing
      .venv/bin/python p18_iltatahti.py            update everything once
      .venv/bin/python p18_iltatahti.py --watch    update everything on every save
      (VS Code: Ctrl+Shift+B, or Terminal > Run Task > "Iltatähti: seuraa muutoksia")
Every update rebuilds the 3D model (OCP viewer, STEP, GLB), the laser SVGs and
the PDF/SVG building drawing from the same parts, so they always agree.
Writes laser/osat*.svg, step/iltatahti_p18.step + .glb, iltatahti_dxf_osat.svg,
piirustus/ILT-P18-001_A.svg + .pdf (A0 drawing, drawing.py)
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from math import atan, atan2, cos, degrees, radians, sin, sqrt, tan
from pathlib import Path

from build123d import (
    Box,
    Color,
    Compound,
    Cylinder,
    Edge,
    Face,
    Location,
    Axis,
    Plane,
    Rot,
    Vector,
    Wire,
    export_gltf,
    export_step,
    extrude,
    import_step,
)
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import split
from shapely.geometry.polygon import orient as shapely_orient

import dxf_parts
import pukki

IN = 25.4
HERE = Path(__file__).parent

# --------------------------------------------------------------------------
# Parameters (mm / degrees)
# --------------------------------------------------------------------------
RULE_WING_SPAN = 18 * IN
RULE_WING_CHORD = 4.5 * IN
RULE_STAB_SPAN = 9 * IN
RULE_STAB_CHORD = 3.5 * IN
RULE_LENGTH = 18 * IN
RULE_HOOK_TO_HOOK = 10 * IN
RULE_PROP_DIA = 6 * IN

# DXF parts, numbers as in iltatahti_dxf_osat.svg
DXF_FILE = HERE / "hyttynen4-indoor-ff-supply-5cm-49cm.dxf"
DXF_OVERVIEW = HERE / "iltatahti_dxf_osat.svg"
MODEL_NAME = "Iltatähti P-18"
MODEL_ID = "iltatahti_p18"  # file names
WING_SPAR_STYLE = 9  # DXF wing spar that the generated spars copy (height, notch depth, root bevel)
WING_HALVES = {  # side: (-1 left / +1 right, length along the spar, root rib, rib 1)
    # root rib = the full (not lightened) DXF rib at the centerline; rib 1 = the lightened
    # one a rib bay out; both have the center spar notch
    "L": (-1, 245.0, 8, 22),  # left wing (-Y), inner half, 1 cm longer
    "R": (1, 235.0, 12, 27),  # right wing (+Y)
}
WING_BAYS = 5  # rib notches per spar = bays + 1 (root rib, full rib, 4 plain ribs as in the DXF)
WING_RIBS = (2, 5, 30, 31, 32, 33, 34, 37, 41, 42, 43)  # identical ribs, used in this order
STAB_SPARS = (17, 23)  # LE, TE
STAB_RIB_LEN_FROM = 3  # DXF stab rib that gives the stab chord
LEGS_FRONT = {"L": 25, "R": 26}
LEGS_REAR = {"L": 35, "R": 36}

# measured from the DXF wing ribs
RIB_TAB_TOP = 1.3  # top of the low end tabs; the flat LE / TE spars lie on them
RIB_STEP_LE = 2.9  # where the rib rises from the LE tab (LE spar notch bottoms here)
RIB_STEP_TE = 77.09  # where the rib rises from the TE tab (TE spar notch bottoms here)
RIB_TAB_CORNER_LE = (3.2, 1.3)  # inner corner of the LE tab (tab top meets the step)
RIB_TAB_CORNER_TE = (76.78, 1.3)  # inner corner of the TE tab
RIB_STEP_TOP = 2.72  # rib top where the step meets the arc (top edge of the spar recess)
RIB_TAB_SLOPE = 14.4  # degrees: the end tabs slope down towards the rib ends (LE and TE alike),
# so the spars lying on them follow the curved upper surface
CENTER_SPAR_X = 40.0  # center spar notch center in the root / full ribs, from the rib LE end
CENTER_SPAR_SEAT = 5.56  # notch bottom height in the root / full ribs
CENTER_SPAR_H = 1.5  # notch depth = center spar height, flush with the rib tops

WING_LE_X = 105.0

# stab: flat, straight ribs
STAB_INCIDENCE = 0.0
STAB_TILT = 5.0  # mm: right tip this much lower, left tip this much higher than level
# stab ribs, flat like the spars (flush top and bottom): (place, width mm);
# place -1 = left tip, 0 = center line (on the stick), 1 = right tip, 0.5 = halfway
STAB_RIBS = [(-1.0, 4.0), (-0.5, 2.0), (0.0, 4.0), (0.5, 2.0), (1.0, 4.0)]

# fin: LE perpendicular to the fuselage, tapers from the root chord to the tip chord
RUDDER_ROOT = 50.0
RUDDER_TIP = 30.0
RUDDER_HEIGHT = 60.0
RUDDER_FRAME_W = 4.0  # frame strip width, frame = 4 strips (grain along each)
RUDDER_JOINT_AMP = 0.22  # S joint wave height as a fraction of the joint length
RUDDER_PIVOT = 20.0  # LE strip reaches this far below the root strip: the hinge of the turning rudder
RUDDER_SIDE = 1  # +1 right / -1 left side of the motor stick, so the pivot runs past the stick
RUDDER_FORWARD = 30.0  # rudder TE root this far ahead of the tail end
RUDDER_TURN = 2.0  # degrees, rudder turned to the left (left turn) about the hinge
RUDDER_HINGE_GAP = 0.1  # hinge clearance to the stick side, so the turned rudder stays clear
RUDDER_STAB_GAP = 0.2  # clearance between the rudder root strip and the stab

# wash-in: left wing LE this much higher at the tip (linear from the root, twist
# about the TE spar). Built with the TE flat on the board and shims under the LE.
WASH_IN_LEFT = 4.0

# thrust line (prop shaft): set in pukki.txt, the mount's bearing is built to it
PUKKI = pukki.read_config()
THRUST_DOWN = PUKKI["alaveto"]  # + = down
THRUST_LEFT = PUKKI["sivuveto"]  # + = left

# balsa
SHEET_T = 2.0  # 2 mm balsa: all DXF parts, spars, ribs, fin
STICK_W = 4.0  # 4 mm balsa: motor stick, wedge
STICK_H = PUKKI["tikun_korkeus"]  # motor stick height, from the nose (pukki.txt: the mount's pocket follows)
STICK_H_TAIL = 4.0  # height at the tail end
STICK_TAPER_LEN = 80.0  # the rear part tapers over this length

# incidence wedge under the wing, on the stick top between the legs.
# Reaches WEDGE_OVERHANG past both the LE and the TE (follows the wing chord),
# thinnest at the rear, top at WEDGE_ANGLE to the stick = wing incidence.
WEDGE_OVERHANG = 5.0
WEDGE_MIN_H = 3.0  # height at the rear end
WEDGE_ANGLE = 2.0
WEDGE_T = STICK_W  # spanwise width = gap between the legs
# notches across the wedge top for the rubber bands that hold the wing: width, depth and
# gap outside the wing's LE / TE (measured from the wing over the wedge)
WEDGE_BAND_NOTCH = (1.0, 1.0, 0.2)
WING_INCIDENCE = WEDGE_ANGLE

# fuselage stations
FRONT_HOOK_X = 16.0  # prop shaft hook, behind the mount's bearing

# 3D printed motor mount (prop below the stick), pukki.py; mount coordinates
MOUNT_POCKET_BOTTOM = pukki.POCKET_BOTTOM  # mount Z of the stick pocket bottom (stick nose against it)
MOUNT_POCKET_TOP = pukki.POCKET_TOP  # mount Y of the pocket top (stick top level with it)
MOUNT_BEARING_Y = pukki.dims(PUKKI)["bearing_y"]  # mount Y of the prop shaft bearing axis (at its front end)
MOUNT_THRUST_Z = MOUNT_BEARING_Y - MOUNT_POCKET_TOP  # thrust line height in the model
HOOK_TO_HOOK = 250.0  # rule 254
STICK_X0 = 10.0
STICK_LEN = 497.0  # a 50 cm balsa strip less ~3 mm, so both ends are cut (1 mm edge margins)
TAIL_END_X = STICK_X0 + STICK_LEN  # stab TE / fin TE / stick end

STEP_DIR = HERE / "step"
# part shapes edited in the laser SVGs (written by sync_all.py): overrides/<part name>.json
OVERRIDE_DIR = HERE / "overrides"

BALSA = Color(0.87, 0.72, 0.53)
PRINT = Color(0.20, 0.35, 0.65)  # 3D printed parts
BALSA_4MM = Color(0.72, 0.52, 0.32)  # darker, so the wedge stands out from the stick
DARK = Color(0.15, 0.15, 0.15)
STEEL = Color(0.75, 0.75, 0.78)


# --------------------------------------------------------------------------
# Flat parts
# --------------------------------------------------------------------------
@dataclass
class FlatPart:
    """A balsa part = 2D profile (local XY) extruded by thickness, placed by plane."""

    name: str
    profile: Face
    thickness: float
    plane: Plane
    grain: float = 0.0  # wood grain direction in the profile, degrees from local X
    color: Color = BALSA
    turns: list = field(default_factory=list)  # [(axis origin, axis direction, degrees)] after placing

    def solid(self, loc: Location = Location()):
        placed = self.plane.location * self.profile
        part = extrude(placed, amount=self.thickness / 2, both=True)
        for origin, direction, angle in self.turns:
            part = part.rotate(Axis(origin, direction), angle)
        part = loc * part
        part.label = self.name
        part.color = self.color
        return part


def make_face(edges) -> Face:
    return Face(Wire(edges))


def rect_profile(length: float, width: float) -> Face:
    """Rectangle length along local X starting at 0, centered on local Y."""
    w = width / 2
    pts = [Vector(0, -w), Vector(length, -w), Vector(length, w), Vector(0, w)]
    return make_face([Edge.make_line(pts[i], pts[(i + 1) % 4]) for i in range(4)])


def polygon_profile(pts) -> Face:
    pts = [Vector(*p) for p in pts]
    return make_face([Edge.make_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))])


# --------------------------------------------------------------------------
# DXF parts
# --------------------------------------------------------------------------
_DXF = None


def dxf_poly(num: int, mirror_x=False, mirror_y=False) -> Polygon:
    """DXF part `num` moved to the origin (bbox min = 0,0), optionally mirrored."""
    global _DXF
    if _DXF is None:
        _DXF, _ = dxf_parts.load_parts(DXF_FILE)
    p = dxf_parts.normalized(_DXF[num - 1], mirror_x)
    if mirror_y:
        p = dxf_parts.normalized(Polygon([(x, -y) for x, y in p.exterior.coords]))
    return p


def dxf_face(num: int, mirror_x=False, mirror_y=False) -> Face:
    p = dxf_poly(num, mirror_x, mirror_y).simplify(0.01)
    return polygon_profile(list(p.exterior.coords)[:-1])


def top_notches(poly: Polygon, min_depth=0.5, max_depth=1.5) -> tuple[list[float], float]:
    """Centers of the notches in the top edge of a strip, and their bottom height.

    The bottom is the most common height inside the notches: the flat notch
    bottoms, not the sloping end bevels that also dip below the top edge.
    """
    from collections import Counter

    x0, _, x1, ymax = poly.bounds
    runs, cur, tops = [], None, Counter()
    n = int((x1 - x0) / 0.05)
    for i in range(n + 1):
        x = x0 + i * (x1 - x0) / n
        cut = poly.intersection(LineString([(x, -1), (x, ymax + 1)]))
        top = cut.bounds[3] if not cut.is_empty else 0.0
        if ymax - max_depth < top < ymax - min_depth:
            tops[round(top, 2)] += 1
            cur = [x, x] if cur is None else [cur[0], x]
        elif cur is not None:
            runs.append(cur)
            cur = None
    if cur is not None:
        runs.append(cur)
    bottom = tops.most_common(1)[0][0] if tops else ymax
    return [(a + b) / 2 for a, b in runs], bottom


# --------------------------------------------------------------------------
# Lifting surfaces (local frame: LE at x=0, rib end bottoms at z=0, centerline y=0)
# --------------------------------------------------------------------------
def rib_plane(origin: Vector, up: Vector) -> Plane:
    x = Vector(1, 0, 0)
    return Plane(origin=origin, x_dir=x, z_dir=x.cross(up))


def strip_plane(origin: Vector, span_dir: Vector, up: Vector) -> Plane:
    """Strip profile: local X along span_dir, local Y up."""
    return Plane(origin=origin, x_dir=span_dir, z_dir=span_dir.cross(up))


def dxf_dihedral() -> float:
    """Each wing half's dihedral from the root bevel of the DXF wing spar.

    The root is the end where the bottom edge is the longer one (V-dihedral).
    """
    p = dxf_poly(WING_SPAR_STYLE, mirror_x=True)
    _, seat = top_notches(p)
    x_top = min(x for x, y in p.exterior.coords if y > seat - 0.01)
    x_bottom = min(x for x, y in p.exterior.coords if y < 0.01)
    return degrees(atan((x_top - x_bottom) / seat))


def spar_style() -> tuple[float, float]:
    """Height of the DXF wing spar and the height of its notch bottoms (rib seat)."""
    p = dxf_poly(WING_SPAR_STYLE)
    return p.bounds[3], top_notches(p)[1]


def spar_low() -> float:
    """Lowest point of the wing below the wing frame: the rib end tab bottoms."""
    return 0.0


def wing_spar_profile(length: float, dih: float) -> tuple[Face, list[float]]:
    """Wing spar like the DXF spar, rib notches SHEET_T wide in one long edge.

    Root at x=0, square: the spar lies flat, so the dihedral joint is through
    its thickness. The root notch takes the vertical root rib and the
    saddle leg beside it (out to the stick side + SHEET_T), the tip notch is at the very end, the others evenly between.
    Returns the profile and the rib stations (notch centers).
    """
    h, seat = spar_style()
    w = SHEET_T
    bevel = 0.0
    root_end = (STICK_W / 2 + SHEET_T) / cos(dih)  # root rib + saddle leg beside it
    first, last = SHEET_T / 2 / cos(dih), length - w / 2
    stations = [first + k * (last - first) / WING_BAYS for k in range(WING_BAYS + 1)]
    pts = [(0, 0), (length, 0), (length, seat), (length - w, seat), (length - w, h)]
    for c in reversed(stations[1:-1]):
        pts += [(c + w / 2, h), (c + w / 2, seat), (c - w / 2, seat), (c - w / 2, h)]
    pts += [(root_end, h), (root_end, seat), (bevel, seat)]
    return polygon_profile(pts), stations


def poly_face(poly: Polygon, tol: float = 0.01) -> Face:
    if tol:
        poly = poly.simplify(tol)
    pts = []
    for c in list(poly.exterior.coords)[:-1]:  # drop repeated points (zero length edges)
        if not pts or (c[0] - pts[-1][0]) ** 2 + (c[1] - pts[-1][1]) ** 2 > 1e-10:
            pts.append(c)
    if (pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2 <= 1e-10:
        pts.pop()
    return polygon_profile(pts)


def notch_corner(poly: Polygon) -> tuple[float, float]:
    """The inner (concave) corner of the single notch in an otherwise convex part."""
    c = list(shapely_orient(poly.simplify(0.01)).exterior.coords)[:-1]
    for i in range(len(c)):
        a, b, d = c[i - 1], c[i], c[(i + 1) % len(c)]
        if (b[0] - a[0]) * (d[1] - b[1]) - (b[1] - a[1]) * (d[0] - b[0]) < -1e-6:  # right turn, CCW ring
            return b
    raise ValueError("no notch")


def saddle_leg(num: int, kind: str) -> tuple[Polygon, tuple[float, float]]:
    """Saddle leg standing along the airflow, notch up at the LE (front) or TE (rear).

    On the DXF sheet the front legs lie with the notch at the bottom left and the
    rear legs are the same shape turned 180 degrees.
    """
    p = dxf_poly(num)
    if kind == "front":
        p = dxf_parts.normalized(affinity.rotate(p, -90, origin=(0, 0)))
    else:
        p = dxf_parts.normalized(affinity.rotate(p, 90, origin=(0, 0)), mirror_x=True)
    return p, notch_corner(p)


def leg_to_stick_bottom(poly: Polygon, o: Vector, chord: float) -> Polygon:
    """Lengthen a saddle leg (bottom edge at y=0) down to the motor stick bottom.

    The leg is placed at `o` in the wing frame, which is tilted by the incidence,
    so each bottom corner gets its own height and the bottom edge ends up level
    with the stick bottom.
    """
    wz, i = wing_mount_z(chord), radians(WING_INCIDENCE)
    coords = []
    y_bottom = poly.bounds[1]  # the bottom edge (not at 0 after the dihedral fit)
    for px, py in poly.exterior.coords:
        if abs(py - y_bottom) < 1e-6:
            x = o.X + px  # wing frame: global Z = wz - x sin(i) + z cos(i)
            py = (-STICK_H - wz + x * sin(i)) / cos(i) - o.Z
        coords.append((px, py))
    return Polygon(coords)


def spar_sink() -> float:
    """How much the LE / TE spars sit lower than on the DXF tabs.

    The recess at the rib end (tab top up to the arc at the step) is 1.5 mm deep:
    the kit was made for 1.5 mm balsa. A SHEET_T spar is sunk so its top is flush
    with the rib top at the step; the rib tabs (and the saddle leg notches) are
    cut down by the same amount where the spar sits (spar_seat_cut).
    """
    a = radians(RIB_TAB_SLOPE)
    cx, cz = RIB_TAB_CORNER_LE
    tab_at_step = cz - (cx - RIB_STEP_LE) * tan(a)
    return max(0.0, SHEET_T / cos(a) - (RIB_STEP_TOP - tab_at_step))


def spar_sections(margin: float = 0.4) -> list[Polygon]:
    """Cross-sections of the sunk LE and TE spars in the rib frame (the part of the
    spar that is not notched, i.e. from the notch bottom out over the rib end)."""
    a = radians(RIB_TAB_SLOPE)
    ca, sa_ = cos(a), sin(a)
    t = SHEET_T + margin
    out = []
    for (cx, cz), step, sgn in ((RIB_TAB_CORNER_LE, RIB_STEP_LE, -1), (RIB_TAB_CORNER_TE, RIB_STEP_TE, 1)):
        cz -= spar_sink()
        u = (sgn * ca, -sa_)  # along the tab, towards the rib end
        n = (sgn * sa_, ca)  # up, perpendicular to the tab
        s1, s2 = abs(cx - step) / ca, 8.0
        pts = [(cx + u[0] * s1, cz + u[1] * s1), (cx + u[0] * s2, cz + u[1] * s2),
               (cx + u[0] * s2 + n[0] * t, cz + u[1] * s2 + n[1] * t), (cx + u[0] * s1 + n[0] * t, cz + u[1] * s1 + n[1] * t)]
        out.append(Polygon(pts))
    return out


def spar_seat_cut(poly: Polygon, offset=(0.0, 0.0), clear: float = 0.0) -> Polygon:
    """Cut the seats of the sunk spars out of a rib-frame part (offset = the part's
    own origin in the rib frame, clear = extra clearance around the spar)."""
    for sec in spar_sections():
        if clear:
            sec = sec.buffer(clear, join_style="mitre")
        poly = poly.difference(affinity.translate(sec, -offset[0], -offset[1]))
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def dihedral_fit(poly: Polygon, y_center: float, dih: float, oz: float = 0.0) -> Polygon:
    """Fit a vertical part at |y| = y_center (root rib, saddle leg) to the dihedral panel.

    The spars run along the dihedral, so at a vertical part a panel height h is
    found at z = h / cos(dih) + y_center * tan(dih). Stretching the profile that way
    puts the LE / TE spars and the center spar into their recesses at the part's
    mid plane. oz = the part's own origin height in the rib frame.
    """
    c, t = cos(dih), tan(dih)
    return affinity.affine_transform(poly, [1, 0, 0, 1 / c, 0, oz / c + y_center * t - oz])


def fit_and_clear(poly: Polygon, y_center: float, dih: float, oz: float = 0.0, clear: float = 0.15,
                  ox: float = 0.0) -> Polygon:
    """dihedral_fit, then clear the seats of the LE / TE spars and the center spar
    by `clear`: the spars cross the 2 mm thick vertical part at the dihedral angle."""
    poly = dihedral_fit(poly, y_center, dih, oz)
    cs = Polygon([(CENTER_SPAR_X - SHEET_T / 2, CENTER_SPAR_SEAT), (CENTER_SPAR_X + SHEET_T / 2, CENTER_SPAR_SEAT),
                  (CENTER_SPAR_X + SHEET_T / 2, CENTER_SPAR_SEAT + 5), (CENTER_SPAR_X - SHEET_T / 2, CENTER_SPAR_SEAT + 5)])
    for sec in spar_sections(margin=0.0) + [cs]:
        sec = affinity.translate(dihedral_fit(sec, y_center, dih), -ox, -oz)  # rib frame -> part frame
        poly = poly.difference(sec.buffer(clear, join_style="mitre"))
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def rib_face(num: int) -> Face:
    """DXF wing rib with the seats of the 2 mm LE / TE spars cut into its end tabs."""
    return poly_face(spar_seat_cut(dxf_poly(num)))


def wing_parts():
    dih = radians(dxf_dihedral())
    chord = dxf_poly(WING_RIBS[0]).bounds[2]
    _, seat = spar_style()
    ribs = list(WING_RIBS)
    parts, spans = [], {}
    for side, (sgn, length, root, full) in WING_HALVES.items():
        d = Vector(0, sgn * cos(dih), sin(dih))
        up = Vector(0, -sgn * sin(dih), cos(dih))
        spar, stations = wing_spar_profile(length, dih)
        # a flat spar tilted by the dihedral leans its top over the centerline: start
        # it so far out that its top corner just meets the centerline
        s0 = (RIB_TAB_TOP + SHEET_T) * tan(dih)
        stations = [s + s0 for s in stations]
        spans[side] = length
        # LE / TE spars lie flat on the rib end tabs (upper surface), notches towards
        # the ribs: the rib rises through the notch, notch bottom at the rib step
        sink = spar_sink()
        mid = up * (RIB_TAB_TOP - sink + SHEET_T / 2)
        for name, edge, toward in (("le", RIB_STEP_LE, 1), ("te", RIB_STEP_TE, -1)):
            ydir = Vector(toward, 0, 0)  # profile Y (notched edge) towards the ribs
            o = Vector(edge - toward * seat, 0, 0) + mid + d * s0
            plane = Plane(origin=o, x_dir=d, z_dir=d.cross(ydir))
            # turn about the tab's inner corner line so that the spar lies on the tab
            # slope: its outer edge goes down, following the curved upper surface
            cx, cz = RIB_TAB_CORNER_LE if name == "le" else RIB_TAB_CORNER_TE
            corner = Vector(cx, 0, 0) + up * (cz - sink) + d * s0
            out = Vector(-toward, 0, 0)  # from the corner towards the rib end
            lift = d.cross(out).Z  # sign of the corner rotation that raises `out`
            slope = (-1 if lift > 0 else 1) * RIB_TAB_SLOPE
            parts.append(FlatPart(f"wing_{side}_{name}_spar", spar, SHEET_T, plane,
                                  turns=[(tuple(corner), tuple(d), slope)]))
        # wash-in (left wing): every rib turns about the TE spar so that the LE rises
        # linearly to WASH_IN_LEFT at the tip rib; the LE spar tilts with them
        wash = WASH_IN_LEFT if side == "L" else 0.0
        le_c = RIB_STEP_LE - seat + spar_style()[0] / 2  # LE spar center line (chordwise)
        te_c = RIB_STEP_TE + seat - spar_style()[0] / 2
        arm = RIB_TAB_CORNER_TE[0] - RIB_TAB_CORNER_LE[0]
        te_axis = Vector(RIB_TAB_CORNER_TE[0], 0, 0) + up * (RIB_TAB_CORNER_TE[1] - sink)  # rib / TE spar contact
        sgn_rib = -1 if d.cross(Vector(1, 0, 0)).Z > 0 else 1  # nose-up rotation sign (LE up about the TE)
        if wash:
            le_root = Vector(le_c, 0, 0) + mid + d * s0
            phi = degrees(atan(wash / (stations[-1] - s0)))
            sgn_up = -1 if Vector(1, 0, 0).cross(d).Z < 0 else 1  # rotation about +X that raises the tip
            parts[-2].turns.append((tuple(le_root), (1, 0, 0), sgn_up * phi))
        # ribs at the notches: root rib, full rib, then plain ribs
        for i, s in enumerate(stations):
            num = root if i == 0 else full if i == 1 else ribs.pop(0)
            if i == 0:  # root ribs stand vertical, side by side at the centerline (2 mm each)
                o = Vector(0, sgn * SHEET_T / 2, 0)
                root_prof = fit_and_clear(spar_seat_cut(dxf_poly(num)), SHEET_T / 2, dih)
                parts.append(FlatPart(f"wing_{side}_rib{i}_{num}", poly_face(root_prof), SHEET_T,
                                      rib_plane(o, Vector(0, 0, 1))))
                continue
            if wash:
                # the twisted rib meets the straight TE spar at a small angle: clear its seat
                rise = wash * (s - s0) / (stations[-1] - s0)
                twist = atan(rise / arm)
                poly = spar_seat_cut(dxf_poly(num), clear=4.2 * tan(twist) + 0.02)
                if i == 1:  # the center spar ends in this rib's notch: clear it for the twist too
                    c_ = 0.1
                    poly = poly.difference(Polygon([(CENTER_SPAR_X - SHEET_T / 2 - c_, CENTER_SPAR_SEAT - c_),
                                                    (CENTER_SPAR_X + SHEET_T / 2 + c_, CENTER_SPAR_SEAT - c_),
                                                    (CENTER_SPAR_X + SHEET_T / 2 + c_, CENTER_SPAR_SEAT + 10),
                                                    (CENTER_SPAR_X - SHEET_T / 2 - c_, CENTER_SPAR_SEAT + 10)]))
                prof = poly_face(poly)
                rib = FlatPart(f"wing_{side}_rib{i}_{num}", prof, SHEET_T, rib_plane(d * s, up))
                rib.turns.append((tuple(te_axis), tuple(d), sgn_rib * degrees(twist)))
            else:
                rib = FlatPart(f"wing_{side}_rib{i}_{num}", rib_face(num), SHEET_T, rib_plane(d * s, up))
            parts.append(rib)
        # center spar: V-dihedral support from the centerline through the full rib,
        # in the rib notches, flush with the rib tops; the root end is cut to the
        # dihedral so the two halves meet vertically at the centerline
        h = CENTER_SPAR_H
        c0 = CENTER_SPAR_SEAT * tan(dih)  # bottom corner on the centerline
        length_cs = stations[1] + SHEET_T / 2
        cs = polygon_profile([(c0, 0), (length_cs, 0), (length_cs, h), (c0 + h * tan(dih), h)])
        o = Vector(CENTER_SPAR_X, 0, 0) + up * CENTER_SPAR_SEAT
        parts.append(FlatPart(f"wing_{side}_center_spar", cs, SHEET_T, strip_plane(o, d, up)))
        if wash:  # the ribs rise at the center spar too: tilt it with them (zero at its root)
            k = (RIB_TAB_CORNER_TE[0] - CENTER_SPAR_X) / arm  # rise here / rise at the LE
            phi_c = degrees(atan(wash * k / (stations[-1] - s0)))
            parts[-1].turns.append((tuple(o), (1, 0, 0), sgn_up * phi_c))
        # saddle legs along the airflow, against the stick side next to the root rib.
        # Their notch is the rib end tab: the LE / TE spar is glued into it.
        y = sgn * (STICK_W + SHEET_T) / 2
        for kind, num in (("front", LEGS_FRONT[side]), ("rear", LEGS_REAR[side])):
            poly, corner = saddle_leg(num, kind)
            rx, ry = RIB_TAB_CORNER_LE if kind == "front" else RIB_TAB_CORNER_TE
            o = Vector(rx - corner[0], y, ry - corner[1])
            poly = spar_seat_cut(poly, (o.X, o.Z))  # same spar seat as in the ribs
            poly = fit_and_clear(poly, (STICK_W + SHEET_T) / 2, dih, o.Z, ox=o.X)
            poly = leg_to_stick_bottom(poly, o, chord)
            parts.append(FlatPart(f"wing_{side}_leg_{kind}_{num}", poly_face(poly), SHEET_T,
                                  rib_plane(o, Vector(0, 0, 1)), grain=90))  # grain upright: a post
    return parts, spans, chord, degrees(dih)


def stab_parts():
    """Flat stab: LE / TE spars and the straight ribs between them all lie flat
    (horizontal), SHEET_T thick so the top and bottom are flush; butt joints.

    Spars are plain strips the size of DXF spars 17 / 23 (no notches); ribs as in
    STAB_RIBS, the tip ribs flush with the tips. Stab bottom at z=0.
    """
    p = dxf_poly(STAB_SPARS[0])
    span, w = p.bounds[2], p.bounds[3]  # 240 x 3.1
    chord = dxf_poly(STAB_RIB_LEN_FROM).bounds[2]
    t = SHEET_T
    parts = []
    spar = polygon_profile([(0, 0), (span, 0), (span, w), (0, w)])
    for name, num, x in (("le", STAB_SPARS[0], 0.0), ("te", STAB_SPARS[1], chord - w)):
        plane = Plane(origin=(x, -span / 2, t / 2), x_dir=(0, 1, 0), z_dir=(0, 0, -1))  # profile Y aft
        parts.append(FlatPart(f"stab_{name}_spar_{num}", spar, t, plane))
    rib_len = chord - 2 * w
    for i, (place, rw) in enumerate(STAB_RIBS):
        s = max(-1.0, min(1.0, place)) * span / 2
        s = max(-span / 2 + rw / 2, min(span / 2 - rw / 2, s))  # tip ribs inside the tips
        rib = polygon_profile([(0, 0), (rib_len, 0), (rib_len, rw), (0, rw)])
        plane = Plane(origin=(w, s + rw / 2, t / 2), x_dir=(1, 0, 0), z_dir=(0, 0, -1))  # profile Y -> -Y
        parts.append(FlatPart(f"stab_rib{i}", rib, t, plane))
    return parts, chord, 0.0, t


def s_joint(a: tuple, b: tuple, ext: float = 1.0, n: int = 32) -> LineString:
    """S-shaped joint line from a to b: one full sine wave across the joint, so
    the two strips interlock and the glued edge is much longer than a butt joint.
    Extended straight by `ext` at both ends to cut cleanly through the frame."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length = sqrt(dx * dx + dy * dy)
    ux, uy = dx / length, dy / length
    amp = RUDDER_JOINT_AMP * length
    pts = [(ax - ux * ext, ay - uy * ext)]
    for k in range(n + 1):
        f = k / n
        off = amp * sin(2 * 3.141592653589793 * f)
        pts.append((ax + dx * f - uy * off, ay + dy * f + ux * off))
    pts.append((b[0] + ux * ext, b[1] + uy * ext))
    return LineString(pts)


def rudder_parts():
    """Rudder frame of 4 strips (LE, root, top, TE) on the side of the motor stick.

    LE vertical (perpendicular to the fuselage) at local x = 0 and RUDDER_PIVOT
    longer than the frame at the bottom: the hinge of the turning rudder. Chord
    RUDDER_ROOT at the root, RUDDER_TIP at the top, so the TE tapers upwards;
    TE root RUDDER_FORWARD ahead of the tail end.

    The frame is cut into its strips along S-shaped interlocking joints for a long
    glued edge: mitred (inner corner to outer corner) at the top and TE corners,
    along the LE strip's edge at the root (the LE runs on down as the hinge).
    The grain runs along every strip.
    """
    w, r, t, h, pv = RUDDER_FRAME_W, RUDDER_ROOT, RUDDER_TIP, RUDDER_HEIGHT, RUDDER_PIVOT
    x0 = TAIL_END_X - RUDDER_FORWARD - r
    outer = Polygon([(0, -pv), (w, -pv), (w, 0), (r, 0), (t, h), (0, h)])
    trap = Polygon([(0, 0), (r, 0), (t, h), (0, h)])
    hole = trap.buffer(-w, join_style="mitre")
    frame = outer.difference(hole)
    hc = {name: min(hole.exterior.coords, key=lambda c: (c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2)
          for name, p in (("le_top", (0, h)), ("le_root", (0, 0)), ("te_root", (r, 0)), ("te_top", (t, h)))}
    joints = [s_joint(hc["le_top"], (0, h)),  # LE / top, mitre
              s_joint((w, 0), hc["le_root"]),  # root against the LE strip's edge
              s_joint(hc["te_root"], (r, 0)),  # root / TE, mitre
              s_joint(hc["te_top"], (t, h))]  # top / TE, mitre
    pieces = list(split(frame, MultiLineString(joints)).geoms)
    te_dir = degrees(atan2(h, t - r))
    names = {  # strip: (a point well inside it, grain direction in the profile)
        "le": ((w / 2, h / 2), 90.0),
        "root": ((r / 2, w / 2), 0.0),
        "top": (((w + t) / 2, h - w / 2), 0.0),
        "te": (((r + t) / 2 - w / 2, h / 2), te_dir),
    }
    y = RUDDER_SIDE * ((STICK_W + SHEET_T) / 2 + RUDDER_HINGE_GAP)
    plane = Plane(origin=(x0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    # turned RUDDER_TURN to the left about the hinge (TE towards -Y)
    hinge = ((x0 + w / 2, y, 0), (0, 0, 1), -RUDDER_TURN)
    parts = []
    for name, (inside, grain) in names.items():
        piece = next(pc for pc in pieces if pc.contains(Point(inside)))
        # no simplification: both sides of a joint must follow the very same curve
        parts.append(FlatPart(f"fin_{name}", poly_face(piece, tol=0), SHEET_T, plane, grain=grain,
                              turns=[hinge]))
    if len(pieces) != 4:
        raise ValueError(f"rudder frame split into {len(pieces)} pieces, expected 4")
    return parts


# --------------------------------------------------------------------------
# Fuselage
# --------------------------------------------------------------------------
def wedge_x(chord: float) -> tuple[float, float]:
    """Front and rear end of the wedge: WEDGE_OVERHANG past the projected LE and TE."""
    te = WING_LE_X + chord * cos(radians(WING_INCIDENCE))
    return WING_LE_X - WEDGE_OVERHANG, te + WEDGE_OVERHANG


def wing_mount_z(chord: float) -> float:
    """Wing frame height so the spar bottoms lie on the wedge top."""
    i = radians(WING_INCIDENCE)
    low = spar_low()
    _, x_rear = wedge_x(chord)
    # local (0, -low) lands at X = LE - low*sin(i), Z = wing_z - low*cos(i) on the wedge top
    return low * cos(i) + WEDGE_MIN_H + (x_rear - WING_LE_X + low * sin(i)) * tan(radians(WEDGE_ANGLE))


def wing_wedge(chord: float) -> FlatPart:
    x0, x1 = wedge_x(chord)
    length = x1 - x0
    h_front = WEDGE_MIN_H + length * tan(radians(WEDGE_ANGLE))
    prof = polygon_profile([(0, 0), (length, 0), (length, WEDGE_MIN_H), (0, h_front)])
    plane = Plane(origin=(x0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return FlatPart("wing_wedge", prof, WEDGE_T, plane, color=BALSA_4MM)


def wedge_with_notches(chord: float, wing_solids) -> FlatPart:
    """The wedge with a WEDGE_BAND_NOTCH notch just in front of the wing's LE and just
    behind its TE: the rubber bands holding the wing sit in them."""
    x0, x1 = wedge_x(chord)
    length = x1 - x0
    slope = tan(radians(WEDGE_ANGLE))
    h_front = WEDGE_MIN_H + length * slope
    band = Location(((x0 + x1) / 2, 0, 20)) * Box(length + 20, WEDGE_T, 60)
    boxes = []
    for s in wing_solids:
        if "_leg_" in (s.label or ""):
            continue
        c = s & band
        if c is not None and c.volume > 1e-6:
            boxes.append(c.bounding_box())
    front, rear = min(b.min.X for b in boxes), max(b.max.X for b in boxes)
    w, d, g = WEDGE_BAND_NOTCH
    poly = Polygon([(0, 0), (length, 0), (length, WEDGE_MIN_H), (0, h_front)])
    for ua, ub in ((front - g - w - x0, front - g - x0), (rear + g - x0, rear + g + w - x0)):
        top_a, top_b = h_front - ua * slope, h_front - ub * slope
        poly = poly.difference(Polygon([(ua, top_a - d), (ub, top_b - d), (ub, h_front + 1), (ua, h_front + 1)]))
    plane = Plane(origin=(x0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return FlatPart("wing_wedge", poly_face(poly), WEDGE_T, plane, color=BALSA_4MM)


def motor_stick():
    """STICK_H x STICK_LEN rectangle from the nose, the rear part tapers to STICK_H_TAIL."""
    prof = polygon_profile([(0, -STICK_H), (STICK_LEN - STICK_TAPER_LEN, -STICK_H),
                            (STICK_LEN, -STICK_H_TAIL), (STICK_LEN, 0), (0, 0)])
    plane = Plane(origin=(STICK_X0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return FlatPart("motor_stick", prof, STICK_W, plane)


def motor_mount():
    """The 3D printed motor mount (pukki.py) on the stick nose.

    In its own coordinates the mount's stick pocket (4 x 10 mm, 10 mm deep) opens
    towards +Z, its arm goes down (-Y) to the prop shaft bearing (axis along Z,
    turned to THRUST_LEFT / THRUST_DOWN). Here: pocket bottom against the stick
    nose, pocket top level with the stick top; mount X -> Y, Y -> Z, Z -> X.
    """
    m = pukki.build_mount(PUKKI)
    loc = Plane(origin=(STICK_X0 - MOUNT_POCKET_BOTTOM, 0, -MOUNT_POCKET_TOP),
                x_dir=(0, 1, 0), z_dir=(1, 0, 0)).location
    m = loc * m
    m.label, m.color = "pukki", PRINT
    return m


def hardware():
    """Non-laser items: 3D printed motor mount, rear hook. The prop (commercial
    6 inch plastic prop below the stick, in the mount's bearing) is not modelled."""
    items = [motor_mount()]
    # rear hook: music wire from the stick bottom down to the thrust line
    length = -STICK_H - MOUNT_THRUST_Z
    hook = Cylinder(0.4, length).moved(Location((FRONT_HOOK_X + HOOK_TO_HOOK, 0, -STICK_H - length / 2)))
    hook.label, hook.color = "rear_hook", STEEL
    items.append(hook)
    return items


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------
def build():
    wing, spans, chord, dihedral = wing_parts()
    stab, stab_chord, stab_seat, stab_spar_top = stab_parts()
    rudder = rudder_parts()
    stick = motor_stick()

    # wing: spars on the incidence wedge, legs on the stick sides (TE down)
    wing_loc = Location((WING_LE_X, 0, wing_mount_z(chord))) * Rot(0, WING_INCIDENCE, 0)
    # stab: bottom on the stick top
    # tilted about the fuselage axis: right tip STAB_TILT lower, left tip higher;
    # lifted so the tilted bottom just clears the stick top edge
    tilt = degrees(atan(STAB_TILT / (dxf_poly(STAB_SPARS[0]).bounds[2] / 2)))
    lift = STICK_W / 2 * tan(radians(tilt))
    stab_loc = Location((TAIL_END_X - stab_chord, 0, stab_seat + lift)) * Rot(-tilt, STAB_INCIDENCE, 0)
    # on the stab, with clearance so the turning rudder clears the stab ribs
    rudder_loc = Location((0, 0, stab_seat + stab_spar_top + lift + RUDDER_STAB_GAP))

    groups = {
        "wing": [(p, wing_loc) for p in wing],
        "stab": [(p, stab_loc) for p in stab],
        "fin": [(p, rudder_loc) for p in rudder],
        "fuselage": [(stick, Location())],
        "wedge": [(wing_wedge(chord), Location())],
    }
    apply_overrides([p for items in groups.values() for p, _ in items])
    solids = {g: [p.solid(loc) for p, loc in items] for g, items in groups.items()}
    if not (OVERRIDE_DIR / "wing_wedge.json").exists():  # rubber band notches (not over a laser edit)
        wedge = wedge_with_notches(chord, solids["wing"])
        groups["wedge"] = [(wedge, Location())]
        solids["wedge"] = [wedge.solid()]
    solids["hardware"] = hardware()
    flat = [p for items in groups.values() for p, _ in items]
    info = dict(spans=spans, chord=chord, dihedral=dihedral, stab_chord=stab_chord)
    return solids, flat, info


def check_rules(solids):
    def bb(group):
        return Compound(solids[group]).bounding_box()

    w, s = bb("wing"), bb("stab")
    allbb = Compound([x for g in solids.values() for x in g]).bounding_box()
    checks = [
        ("wing projected span", w.size.Y, RULE_WING_SPAN),
        ("wing chord (projected)", w.size.X, RULE_WING_CHORD),
        ("stab span", s.size.Y, RULE_STAB_SPAN),
        ("stab chord", s.size.X, RULE_STAB_CHORD),
        ("overall length incl. prop", allbb.max.X - min(allbb.min.X, 0), RULE_LENGTH),
        ("hook to hook", HOOK_TO_HOOK, RULE_HOOK_TO_HOOK),
    ]
    ok = True
    print("\nP-18 rule check")
    for name, val, lim in checks:
        good = val <= lim
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name:28s} {val:7.1f} mm  (max {lim:.1f})")
    return ok


# --------------------------------------------------------------------------
# SVG check: every drawn line must be an Inkscape hairline
# --------------------------------------------------------------------------
HAIRLINE = {"stroke-width": ("1px", "1"), "vector-effect": ("non-scaling-stroke",),
            "-inkscape-stroke": ("hairline",)}
SVG_SHAPES = {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse", "text"}


def _style(el, inherited: dict) -> dict:
    st = dict(inherited)
    for k in ("stroke", "stroke-width", "vector-effect", "fill"):
        if k in el.attrib:
            st[k] = el.attrib[k].strip()
    for decl in el.attrib.get("style", "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            st[k.strip()] = v.strip()
    return st


def check_hairlines(files) -> bool:
    """Every stroked element in the SVG files must be an Inkscape hairline.

    Filled shapes without a stroke (engraved numbers, text) are not lines.
    """
    lines, bad = 0, []

    def walk(el, inherited, path):
        nonlocal lines
        st = _style(el, inherited)
        tag = el.tag.split("}")[-1]
        if tag in SVG_SHAPES and st.get("stroke", "none") != "none":
            lines += 1
            wrong = [f"{k}={st.get(k)}" for k, ok in HAIRLINE.items() if st.get(k) not in ok]
            if wrong:
                bad.append(f"{path.name}: <{tag} id={el.attrib.get('id', '-')}> {', '.join(wrong)}")
        for ch in el:
            walk(ch, st, path)

    for f in files:
        f = Path(f)
        walk(ET.parse(f).getroot(), {}, f)
    print(f"\nHairline check: {lines} lines in {len(files)} SVG files", end="")
    if bad:
        print(f" -> {len(bad)} NOT hairline:")
        for b in bad[:20]:
            print(f"  FAIL {b}")
        return False
    print(" -> all Inkscape hairline")
    return True


def apply_overrides(parts) -> list[str]:
    """Replace the profiles of parts whose shape was edited in a laser SVG.

    overrides/<part name>.json holds the edited outline (and holes) in the part's own
    coordinates; sync_all.py writes it. Delete the file to go back to the model.
    """
    import json

    used = []
    for p in parts:
        f = OVERRIDE_DIR / f"{p.name}.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text())

        def wire(pts):
            pts = [Vector(*q) for q in pts]
            return Wire([Edge.make_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))])
        p.profile = Face(wire(data["outer"]), [wire(h) for h in data.get("holes", [])])
        used.append(p.name)
    if used:
        print(f"laserista muokatut osat (overrides/): {', '.join(used)}")
    return used


# --------------------------------------------------------------------------
# Update everything: 3D model, laser SVGs, building drawing
# --------------------------------------------------------------------------
# A change in any of these files makes --watch rebuild everything
WATCH_FILES = [Path(__file__), HERE / "to_laser.py", HERE / "drawing.py", HERE / "dxf_parts.py",
               DXF_FILE, HERE / "pukki.py", pukki.CONFIG]


def update_all(viewer=True, outputs=("3d", "laser", "drawing")):
    """Rebuild the model and write the chosen outputs from the same parts.

    outputs: "3d" (STEP, GLB, OCP viewer), "laser" (laser SVGs) and/or "drawing"
    (A0 PDF/SVG). Returns {"laser": [written laser SVG files]}.
    """
    result = {"laser": []}
    import sys

    sys.modules.setdefault("p18_iltatahti", sys.modules[__name__])  # to_laser / drawing reuse this module
    dxf_parts.write_overview(DXF_FILE, DXF_OVERVIEW)
    solids, flat, info = build()
    sp = info["spans"]
    print(f"wing: halves {sp['L']:.1f} + {sp['R']:.1f} = {sp['L'] + sp['R']:.1f} mm along the spars, "
          f"chord {info['chord']:.1f} mm, dihedral {info['dihedral']:.2f} deg each half (DXF)")
    check_rules(solids)

    # 3D files for other programs: STEP (CAD) and glTF binary (viewers, Blender, web)
    if "3d" not in outputs:
        viewer = False
    STEP_DIR.mkdir(exist_ok=True)
    assembly = Compound(label=MODEL_NAME, children=[Compound(children=v, label=k) for k, v in solids.items()])
    if "3d" in outputs:
        export_step(assembly, STEP_DIR / f"{MODEL_ID}.step")
        export_gltf(assembly, str(STEP_DIR / f"{MODEL_ID}.glb"), binary=True)
        print(f"\n3D: {STEP_DIR.name}/{MODEL_ID}.step, {STEP_DIR.name}/{MODEL_ID}.glb")
        files = pukki.write_outputs(PUKKI)  # the mount alone, for the 3D printer
        print(f"pukki: sivuveto {THRUST_LEFT:g}° vasemmalle, alaveto {THRUST_DOWN:g}°, "
              f"tasku 4×{STICK_H + PUKKI['taskun_vara']:g} (tikku {STICK_H:g}), laakerireikä "
              f"⌀{PUKKI['laakerireika']:g} -> {', '.join(f'{STEP_DIR.name}/{f.name}' for f in files)}")

    # laser SVGs from the same parts
    if "laser" in outputs:
        import to_laser

        print("\nLaser:")
        svgs = to_laser.main(flat, quiet=True)
        check_hairlines(svgs + [DXF_OVERVIEW])
        result["laser"] = [f for f in svgs if f.parent.name == "laser"]

    # A0 building drawing (SVG + PDF, main views 1:1) from the same build
    if "drawing" in outputs:
        import drawing

        print("\nPiirustus:")
        for f in drawing.make((solids, flat, info)):
            print(f"  {f.relative_to(HERE)}")

    if viewer:
        try:
            from ocp_vscode import Camera, show

            show(*[Compound(children=v, label=k) for k, v in solids.items()],
                 names=list(solids.keys()), reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"\nOCP viewer not available: {e}")
    return result


def watch(viewer=True, interval=1.0):
    """Rebuild everything whenever a watched file is saved (Ctrl+C stops).

    Each rebuild runs in a fresh Python process, so edits to any of the
    scripts take effect without restarting the watcher.
    """
    import subprocess
    import sys
    import time

    def stamp():
        return {f: f.stat().st_mtime for f in WATCH_FILES if f.exists()}

    cmd = [sys.executable, str(Path(__file__).resolve())] + ([] if viewer else ["--no-viewer"])
    print("Seurataan:", ", ".join(f.name for f in WATCH_FILES))
    last = stamp()
    subprocess.run(cmd)
    print(f"\n[{time.strftime('%H:%M:%S')}] valmis — odotetaan muutoksia (Ctrl+C lopettaa)")
    try:
        while True:
            time.sleep(interval)
            now = stamp()
            if now != last:
                changed = [f.name for f in now if now.get(f) != last.get(f)]
                time.sleep(0.5)  # let the editor finish writing
                last = stamp()
                print(f"\n[{time.strftime('%H:%M:%S')}] muuttui: {', '.join(changed)} — päivitetään kaikki")
                subprocess.run(cmd)
                print(f"[{time.strftime('%H:%M:%S')}] valmis — odotetaan muutoksia")
    except KeyboardInterrupt:
        print("\nSeuranta lopetettu.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=f"{MODEL_NAME}: 3D-malli, laser-SVG:t ja rakennuspiirustus")
    ap.add_argument("--watch", action="store_true", help="päivitä kaikki aina kun lähdetiedosto tallennetaan")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    args = ap.parse_args()
    if args.watch:
        watch(viewer=not args.no_viewer)
    else:
        update_all(viewer=not args.no_viewer)
