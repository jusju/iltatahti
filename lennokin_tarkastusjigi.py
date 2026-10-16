"""
lennokin_tarkastusjigi.py — alignment jig for the whole Iltatähti P-18, cut by laser
from the same 6 mm balsa board as the wing jig (83 mm wide, 2330 mm long).

The finished model is locked on the jig by its motor stick in two cradles (snug 4 mm
slots). Every check is a straight reference edge 5 mm from the part it checks: slide a
5 mm gauge block (or a 5 mm drill shank) along the gap; the gap must be the same all
the way.

  wing          LE and TE reference edges under the spars over the whole span, along
                the dihedral; the left LE edge rises with the wash-in. The height
                difference of the LE and TE edges is the wing incidence.
  stab          LE and TE reference edges under the stab spars, tilted ±5 mm: the stab
                must be flat (same gap everywhere) and tilted the right amount.
  thrust line   with the prop off and a straight 1 mm piano wire through the bearing:
                a long bottom guide 5 mm below the wire and a side guide 5 mm to its
                right, both along the designed thrust line (side and down thrust).

All parts stand on the table (z = TABLE), egg-crated into two rails along the model.
The reference lines are measured from the model (p18_iltatahti.py, pukki.txt), and the
whole model is placed on the jig to check every gap and the incidence, tilt and thrust.

Writes
  laser/jigi_tarkastus1.svg      all parts (…2.svg if a second board piece is needed),
                                 hairline cuts with 1 mm tabs, engraved numbers
  step/jigi_tarkastus.step       the jig
Run:  .venv/bin/python lennokin_tarkastusjigi.py [--no-viewer]
"""

import argparse
from math import atan, cos, degrees, radians, sin, tan
from pathlib import Path

import numpy as np
from build123d import Align, Box, Compound, Cylinder, Location, Plane, export_step
from shapely.geometry import Polygon

import p18_iltatahti as m
import vasemman_siiven_jigi as wj

HERE = Path(__file__).parent
STEP_FILE = HERE / "step" / "jigi_tarkastus.step"
JIG_ID = "jigi-tarkastus"
T, SLOT = wj.T, wj.SLOT

GAP_REF = 5.0  # every reference edge is this far from the part it checks
TABLE = -41.5  # table level (the model's stick top is z 0); the tallest part fits the board
RAIL_Y, RAIL_H = 30.0, 20.0  # two rails along the model at y = ±RAIL_Y
X_FRONT, X_REAR = -255.0, 515.0  # rails from the thrust guide's front end to behind the tail
CROSS_W = 90.0  # cradles and guide beams: width across
CRADLES_X = (60.0, 380.0)  # motor stick cradles (in front of the wing, before the tail taper)
STICK_SLOT = 3.9  # cradle slot for the 4 mm stick: the laser kerf opens it to a snug 4.0
WING_NOTCH, STAB_NOTCH = 8.0, 4.0  # half widths of the center notches (stick, legs, wedge)
NOTCH_BELOW = 3.0  # notch bottoms this far below the stick bottom
WING_HALF, STAB_HALF = 246.0, 128.0  # reference edges reach this far out (y)
GUIDE_X = (-5.0, -255.0)  # thrust guides from / to
GUIDE_BEAMS_X = (-25.0, -235.0)
GUIDE_H_ABOVE = 10.0  # side guide's top above the wire
WIRE_R = 0.5  # 1 mm piano wire in the bearing instead of the prop
JIG_COLOR = m.Color(0.55, 0.40, 0.25)


# --------------------------------------------------------------------------
# measurements from the model
# --------------------------------------------------------------------------
def spar_bottom(s, y):
    """Lowest z and middle x of solid s in a thin slice at span position y."""
    b = s.bounding_box()
    c = s & (Location((b.center().X, y, b.center().Z)) * Box(2000, 0.6, 2000))
    if c is None or c.volume < 1e-6:
        return None
    cb = c.bounding_box()
    return cb.min.Z, cb.center().X


def fit_line(s, ys):
    pts = [(y, *spar_bottom(s, y)) for y in ys]
    y, z, x = (np.array(v) for v in zip(*pts))
    k, c = np.polyfit(y, z, 1)
    return dict(k=k, c=c, x=float(x.mean()), dev=float(np.abs(z - (k * y + c)).max()))


def stick_bottom(stick, x):
    return (stick & (Location((x, 0, 0)) * Box(0.6, 50, 50))).bounding_box().min.Z


def thrust_line():
    """Prop shaft axis from the bearing front: point(d) for plan distance d forward."""
    a, b = radians(m.THRUST_LEFT), radians(m.THRUST_DOWN)
    x0 = m.STICK_X0 - m.MOUNT_POCKET_BOTTOM + m.pukki.BEARING_Z0
    z0 = m.MOUNT_THRUST_Z

    def at(d, off=0.0):  # off: sideways to the right (+y side) of the line
        return (x0 - d * cos(a) - off * sin(a), -d * sin(a) + off * cos(a), z0 - d * tan(b))
    return a, b, x0, at


def measure(solids):
    n = {s.label: s for g in solids.values() for s in g}
    yl, yr = np.linspace(-225, -20, 10), np.linspace(20, 225, 10)
    ys = list(np.linspace(-110, -12, 6)) + list(np.linspace(12, 110, 6))
    stab_le = next(k for k in n if k.startswith("stab_le_spar"))
    stab_te = next(k for k in n if k.startswith("stab_te_spar"))
    return dict(
        le=(fit_line(n["wing_L_le_spar"], yl), fit_line(n["wing_R_le_spar"], yr)),
        te=(fit_line(n["wing_L_te_spar"], yl), fit_line(n["wing_R_te_spar"], yr)),
        stab_le=fit_line(n[stab_le], ys), stab_te=fit_line(n[stab_te], ys),
        stick=n["motor_stick"], names=n, stab_names=(stab_le, stab_te))


# --------------------------------------------------------------------------
# parts: (name, polygon (u, v), plane origin, x_dir, z_dir)
# --------------------------------------------------------------------------
def poly_cut(poly, cuts):
    for u0, v0, u1, v1 in cuts:
        poly = poly.difference(Polygon([(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))
    return poly.simplify(1e-6)


def cross_piece(name, x, y0, y1, top, cuts=()):
    """Piece across the model at x, from y0 to y1, on the table; top(y) -> z of its top
    edge (straight pieces between the given break points)."""
    ys = sorted(set([y0, y1] + [y for y in top.breaks if y0 < y < y1]))
    pts = [(0, 0), (y1 - y0, 0)] + [(y - y0, top(y) - TABLE) for y in reversed(ys)]
    rails = [(y - y0 - SLOT / 2, 0, y - y0 + SLOT / 2, RAIL_H / 2) for y in (-RAIL_Y, RAIL_Y)]
    poly = poly_cut(Polygon(pts), rails + [(a - y0, b - TABLE, c - y0, d - TABLE) for a, b, c, d in cuts])
    return (name, poly, (x, y0, TABLE), (0, 1, 0), (1, 0, 0))


class Top:
    """Top edge as z(y) with break points (piecewise straight)."""
    def __init__(self, f, breaks=()):
        self.f, self.breaks = f, list(breaks)

    def __call__(self, y):
        return self.f(y)


def jig_parts(meas):
    st = meas["stick"]
    a, b, x0, at = thrust_line()
    parts = []
    # rails
    xs = [GUIDE_BEAMS_X[1], GUIDE_BEAMS_X[0], CRADLES_X[0], meas["le"][0]["x"], meas["te"][0]["x"],
          CRADLES_X[1], meas["stab_le"]["x"], meas["stab_te"]["x"]]
    length = X_REAR - X_FRONT
    for name, y in (("kisko vasen", -RAIL_Y), ("kisko oikea", RAIL_Y)):
        poly = poly_cut(Polygon([(0, 0), (length, 0), (length, RAIL_H), (0, RAIL_H)]),
                        [(x - X_FRONT - SLOT / 2, RAIL_H / 2, x - X_FRONT + SLOT / 2, RAIL_H + 1) for x in xs])
        parts.append((name, poly, (X_FRONT, y, TABLE), (1, 0, 0), (0, -1, 0)))
    # thrust guide beams: slots from above where the two guides cross (at the thrust angle)
    w_ang = T / cos(a) + T * tan(a)
    guides = [("vetoviivan alaohjain", 0.0, lambda d: at(d)[2] - GAP_REF - WIRE_R),
              ("vetoviivan sivuohjain", GAP_REF + WIRE_R + T / 2, lambda d: at(d)[2] + GUIDE_H_ABOVE)]
    for name, xb in (("vetoviivan ohjaimen etupalkki", GUIDE_BEAMS_X[1]), ("vetoviivan ohjaimen takapalkki", GUIDE_BEAMS_X[0])):
        cuts = []
        for _, off, _ in guides:
            d = (x0 - off * sin(a) - xb) / cos(a)
            y = at(d, off)[1]
            cuts.append((y - w_ang / 2, TABLE + RAIL_H / 2, y + w_ang / 2, TABLE + RAIL_H + 1))
        parts.append(cross_piece(name, xb, -CROSS_W / 2, CROSS_W / 2, Top(lambda y: TABLE + RAIL_H), cuts))
    # motor stick cradles
    for name, xc in (("rungon etukannatin", CRADLES_X[0]), ("rungon takakannatin", CRADLES_X[1])):
        zb = stick_bottom(st, xc)
        parts.append(cross_piece(name, xc, -CROSS_W / 2, CROSS_W / 2, Top(lambda y: 0.0),
                                 [(-STICK_SLOT / 2, zb, STICK_SLOT / 2, 1.0)]))
    # wing reference edges: per half the spar bottom line less GAP_REF; notch at the center
    for name, (fl, fr), in (("siiven johtoreunan vertailu", meas["le"]), ("siiven jättöreunan vertailu", meas["te"])):
        x = (fl["x"] + fr["x"]) / 2
        zb = stick_bottom(st, x)

        def top(y, fl=fl, fr=fr):
            f = fl if y < 0 else fr
            return f["k"] * y + f["c"] - GAP_REF
        parts.append(cross_piece(name, x, -WING_HALF, WING_HALF, Top(top, [-WING_NOTCH, WING_NOTCH]),
                                 [(-WING_NOTCH, zb - NOTCH_BELOW, WING_NOTCH, 200)]))
    # stab reference edges: one straight tilted line, notch for the stick
    for name, f in (("vakaajan johtoreunan vertailu", meas["stab_le"]), ("vakaajan jättöreunan vertailu", meas["stab_te"])):
        zb = stick_bottom(st, min(f["x"], m.TAIL_END_X - 0.5))
        parts.append(cross_piece(name, f["x"], -STAB_HALF, STAB_HALF,
                                 Top(lambda y, f=f: f["k"] * y + f["c"] - GAP_REF, [-STAB_NOTCH, STAB_NOTCH]),
                                 [(-STAB_NOTCH, zb - NOTCH_BELOW, STAB_NOTCH, 200)]))
    # thrust guides along the thrust line, from GUIDE_X[1] (front) to GUIDE_X[0]
    d_f, d_r = (x0 - GUIDE_X[1]) / cos(a), (x0 - GUIDE_X[0]) / cos(a)
    rear = (cos(a), sin(a), 0.0)
    for name, off, top in guides:
        L = d_f - d_r
        cuts = []
        for xb in GUIDE_BEAMS_X:
            d = (x0 - off * sin(a) - xb) / cos(a)
            u = d_f - d
            cuts.append((u - w_ang / 2, 0, u + w_ang / 2, RAIL_H / 2))
        poly = poly_cut(Polygon([(0, 0), (L, 0), (L, top(d_r) - TABLE), (0, top(d_f) - TABLE)]), cuts)
        sx, sy, _ = at(d_f, off)
        parts.append((name, poly, (sx, sy, TABLE), rear, (sin(a), -cos(a), 0.0)))
    return parts


def wire_solid():
    """Straight 1 mm piano wire in the bearing (prop off), for the check."""
    a, b, x0, at = thrust_line()
    d0, d1 = -12.0, (x0 - GUIDE_X[1]) / cos(a) + 5
    p0, p1 = np.array(at(d0)), np.array(at(d1))
    axis = (p1 - p0) / np.linalg.norm(p1 - p0)
    w = Plane(origin=tuple(p0), z_dir=tuple(axis)).location * Cylinder(WIRE_R, float(np.linalg.norm(p1 - p0)),
                                                                        align=(Align.CENTER, Align.CENTER, Align.MIN))
    w.label, w.color = "pianolanka (potkurin tilalla)", m.STEEL
    return w


# --------------------------------------------------------------------------
def build():
    solids, flat, info = m.build()
    meas = measure(solids)
    parts = jig_parts(meas)
    jig = []
    for n, (name, poly, origin, x_dir, z_dir) in enumerate(parts, 1):
        s = wj.solid_of(poly, origin, x_dir, z_dir)
        s.label, s.color = f"{n} {name}", JIG_COLOR
        jig.append(s)
    aircraft = [s for g in solids.values() for s in g]
    return dict(parts=parts, jig=jig, aircraft=aircraft, wire=wire_solid(), meas=meas)


def vol(c):
    return 0 if c is None else (c.volume if hasattr(c, "volume") else sum(x.volume for x in c))


def validate(bld):
    """The whole model on the jig: gaps along every reference edge, incidence, tilt, thrust."""
    jig, meas, n = bld["jig"], bld["meas"], bld["meas"]["names"]
    by = {s.label.split(" ", 1)[1]: s for s in jig}

    def ref_top(piece, y):
        c = piece & (Location((piece.bounding_box().center().X, y, 0)) * Box(50, 0.6, 400))
        return c.bounding_box().max.Z

    print("Raot vertailureunoihin (tavoite 5,00 mm koko matkalla):")
    checks = [("siiven johtoreunan vertailu", "wing_L_le_spar", np.linspace(-230, -15, 8)),
              ("siiven johtoreunan vertailu", "wing_R_le_spar", np.linspace(15, 225, 8)),
              ("siiven jättöreunan vertailu", "wing_L_te_spar", np.linspace(-230, -15, 8)),
              ("siiven jättöreunan vertailu", "wing_R_te_spar", np.linspace(15, 225, 8)),
              ("vakaajan johtoreunan vertailu", meas["stab_names"][0], list(np.linspace(-118, -8, 6)) + list(np.linspace(8, 118, 6))),
              ("vakaajan jättöreunan vertailu", meas["stab_names"][1], list(np.linspace(-118, -8, 6)) + list(np.linspace(8, 118, 6)))]
    for ref, part, ys in checks:
        gaps = [spar_bottom(n[part], y)[0] - ref_top(by[ref], y) for y in ys]
        print(f"  {ref:32s} / {part:16s} {min(gaps):5.2f} … {max(gaps):5.2f} mm")
    # thrust: wire vs the guides
    w = bld["wire"]
    g1, g2 = by["vetoviivan alaohjain"], by["vetoviivan sivuohjain"]
    below, side = [], []
    for x in np.linspace(GUIDE_X[1] + 10, GUIDE_X[0] - 10, 6):
        sl = Location((x, 0, 0)) * Box(0.6, 400, 400)
        wb, b1, b2 = (w & sl).bounding_box(), (g1 & sl).bounding_box(), (g2 & sl).bounding_box()
        below.append(wb.min.Z - b1.max.Z)
        side.append(b2.min.Y - wb.max.Y)
    print(f"  {'vetoviivan alaohjain':32s} / pianolanka       {min(below):5.2f} … {max(below):5.2f} mm (pystysuunta)")
    print(f"  {'vetoviivan sivuohjain':32s} / pianolanka       {min(side):5.2f} … {max(side):5.2f} mm (vaakasuunta, "
          f"leikkaus x-tasossa)")
    # angles read from the reference edges
    le, te = meas["le"], meas["te"]
    for side_, i in (("vasen", 0), ("oikea", 1)):
        for y in ((-40, -230) if i == 0 else (40, 225)):
            zl, zt = le[i]["k"] * y + le[i]["c"], te[i]["k"] * y + te[i]["c"]
            inc = degrees(atan((zl - zt) / (te[i]["x"] - le[i]["x"])))
            print(f"Asetuskulma {side_} y {y:+5.0f}: {inc:4.2f}° (johto- ja jättöreunan vertailun korkeusero "
                  f"{zl - zt:4.2f} mm / {te[i]['x'] - le[i]['x']:.1f} mm)")
    s = meas["stab_le"]
    print(f"Vakaajan tiltti: vertailureuna y −120 {s['k'] * -120 + s['c'] - GAP_REF:+.2f}, y +120 "
          f"{s['k'] * 120 + s['c'] - GAP_REF:+.2f} mm (ero {-240 * s['k']:.2f} mm, ±{-120 * s['k']:.2f} mm)")
    print(f"Vetoviiva: {m.THRUST_LEFT:g}° vasemmalle, {m.THRUST_DOWN:g}° alas (pukki.txt); ohjaimet ovat sen suuntaiset")
    # straightness of the model parts themselves (deviation from a straight line)
    print("Mallin rimojen suoruus (poikkeama suorasta): " + ", ".join(
        f"{k} {v:.3f}" for k, v in (("siipi JR v", le[0]["dev"]), ("siipi JR o", le[1]["dev"]), ("siipi JäR v", te[0]["dev"]),
                                     ("siipi JäR o", te[1]["dev"]), ("vakaaja JR", meas["stab_le"]["dev"]),
                                     ("vakaaja JäR", meas["stab_te"]["dev"]))) + " mm")
    # collisions
    jc = Compound(jig)
    hit = {}
    for a_ in bld["aircraft"] + [w]:
        v = vol(a_.intersect(jc))
        if v > 0.01:
            hit[a_.label] = v
    over = sum(vol(x.intersect(y)) for i, x in enumerate(jig) for y in jig[i + 1:])
    print(f"Jigin osat päällekkäin {over:.3f} mm³; lennokki ja jigi: " +
          (", ".join(f"{k} {v:.2f} mm³" for k, v in hit.items()) if hit else "ei kosketusta") +
          f" (runkotikku kannattimissa = tiukka sovite {STICK_SLOT:g} mm)")


def main(viewer=True):
    bld = build()
    validate(bld)
    wj.LASER_DIR.mkdir(exist_ok=True)
    files = wj.laser(bld["parts"], stem="jigi_tarkastus", jig_id=JIG_ID, what="lennokin tarkastusjigi")
    print("\nOsat:")
    for n, (name, poly, *_) in enumerate(bld["parts"], 1):
        b = poly.bounds
        print(f"  {n:2d}  {name:32s} {b[2] - b[0]:6.1f} × {b[3] - b[1]:4.1f} mm")
    for path, used, sheet in files:
        print(f"Laser: {path.relative_to(HERE)}: {len(sheet.placed)} osaa, balsaa {used} × {wj.BOARD_W:g} × {T:g} mm")
    STEP_FILE.parent.mkdir(exist_ok=True)
    jig = Compound(children=bld["jig"], label="jigi_tarkastus")
    export_step(jig, STEP_FILE)
    print(f"3D: {STEP_FILE.relative_to(HERE)}")
    if viewer:
        try:
            from ocp_vscode import Camera, show

            plane = Compound(children=bld["aircraft"] + [bld["wire"]], label="lennokki (tarkistus)")
            show(jig, plane, names=["tarkastusjigi", "lennokki (tarkistus)"], reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Koko lennokin tarkastusjigi 6 mm balsasta")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
