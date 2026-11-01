"""
lennokin_tarkastusjigi.py — alignment jig for the whole Iltatähti P-18, cut by laser
from the same 6 mm balsa board as the wing jig (83 mm wide, 2330 mm long).

The finished model is locked on the jig by its motor stick in two cradles (snug 4 mm
slots). Every check is a straight reference edge 5 mm from the part it checks: slide a
5 mm gauge block (or a 5 mm drill shank) along the gap; the gap must be the same all
the way.

  wing          LE and TE reference edges under the spars over the whole span, along
                the dihedral; the left LE edge rises with the wash-in. The height
                difference of the LE and TE edges is the wing incidence. They end where
                the spars end: the left half (1 cm longer) and the right half must end
                flush with them.
  stab          LE and TE reference edges under the stab spars, tilted ±5 mm: the stab
                must be flat (same gap everywhere) and tilted the right amount.
  side thrust   with the prop turned level (blades across), a plate right behind it,
                parallel to the prop disc of the designed thrust line: the gap from
                the plate to the blade tips is 5 mm at both tips when the side thrust is
                right; 1 mm difference between the tips is about 0.38°.

All parts stand on the table (z = TABLE), egg-crated into two rails along the model.
The reference lines are measured from the model (p18_iltatahti.py, pukki.txt), and the
whole model is placed on the jig to check every gap and the incidence, tilt and thrust.
Only the jig is cut: the model's own parts are in the laser files of p18_iltatahti.py.

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

import drawing
import p18_iltatahti as m
import vasemman_siiven_jigi as wj

HERE = Path(__file__).parent
STEP_FILE = HERE / "step" / "jigi_tarkastus.step"
JIG_ID = "jigi-tarkastus"
T, SLOT = wj.T, wj.SLOT

GAP_REF = 5.0  # every reference edge is this far from the part it checks
TABLE = -41.5  # table level (the model's stick top is z 0); the tallest part fits the board
RAIL_Y, RAIL_H = 30.0, 20.0  # two rails along the model at y = ±RAIL_Y
X_REAR = 515.0  # rails from just in front of the prop plate to behind the tail
CROSS_W = 76.0  # cradles: width across
CRADLES_X = (60.0, 380.0)  # motor stick cradles (in front of the wing, before the tail taper)
STICK_SLOT = 3.9  # cradle slot for the 4 mm stick: the laser kerf opens it to a snug 4.0
WING_NOTCH, STAB_NOTCH = 8.0, 4.0  # half widths of the center notches (stick, legs, wedge)
NOTCH_BELOW = 3.0  # notch bottoms this far below the stick bottom
# the wing and stab reference edges end exactly at the spar tips (span check)
PROP_HALF = 85.0  # prop plate reaches this far out on both sides (the 6" prop: 76)
PROP_TIP = 15.0  # the blade tips: the outer 15 mm of each blade
PROP_TOP_ABOVE = 10.0  # prop plate's top above the shaft
PROP_NOTCH = 6.0  # half width of its notch for the mount and the stick
JIG_COLOR = m.Color(0.55, 0.40, 0.25)


# --------------------------------------------------------------------------
# measurements from the model
# --------------------------------------------------------------------------
SLICE = 0.1  # thickness of the measuring slices


def spar_bottom(s, y):
    """Lowest z, middle x, front x, rear x of solid s in a thin slice at span position y."""
    b = s.bounding_box()
    c = s & (Location((b.center().X, y, b.center().Z)) * Box(2000, SLICE, 2000))
    if c is None or c.volume < 1e-9:
        return None
    cb = c.bounding_box()
    return cb.min.Z, cb.center().X, cb.min.X, cb.max.X


def fit_line(s, ys):
    pts = [(y, *spar_bottom(s, y)) for y in ys]
    y, z, x, x0, x1 = (np.array(v) for v in zip(*pts))
    k, c = np.polyfit(y, z, 1)
    return dict(k=k, c=c, x=float(x.mean()), x_front=float(x0.mean()), x_rear=float(x1.mean()),
                dev=float(np.abs(z - (k * y + c)).max()))


def ref_x(meas, key):
    """x of a wing reference edge: the middle of the left and right spar."""
    return (meas[key][0]["x"] + meas[key][1]["x"]) / 2


def stick_bottom(stick, x):
    return (stick & (Location((x, 0, 0)) * Box(0.6, 50, 50))).bounding_box().min.Z


def prop_plate_line(prop, hub, fwd):
    """Rear unit vector, across unit vector (to the right), blade tip positions behind
    the hub (rearmost point of each tip, along the shaft)."""
    a = radians(m.THRUST_LEFT)
    rear = (cos(a), sin(a), 0.0)
    across = (-sin(a), cos(a), 0.0)
    R = m.RULE_PROP_DIA / 2
    tips = {-1: -1e9, 1: -1e9}
    for v in prop.vertices():
        d = (v.X - hub.X, v.Y - hub.Y, v.Z - hub.Z)
        back = sum(d[i] * rear[i] for i in range(3))
        lat = sum(d[i] * across[i] for i in range(3))
        if abs(lat) > R - PROP_TIP:
            side = 1 if lat > 0 else -1
            tips[side] = max(tips[side], back)
    return rear, across, tips


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
        stick=n["motor_stick"], names=n, stab_names=(stab_le, stab_te), mount=n["pukki"],
        tips={"le": (n["wing_L_le_spar"].bounding_box().min.Y, n["wing_R_le_spar"].bounding_box().max.Y),
              "te": (n["wing_L_te_spar"].bounding_box().min.Y, n["wing_R_te_spar"].bounding_box().max.Y),
              "stab_le": (n[stab_le].bounding_box().min.Y, n[stab_le].bounding_box().max.Y),
              "stab_te": (n[stab_te].bounding_box().min.Y, n[stab_te].bounding_box().max.Y)})


# --------------------------------------------------------------------------
# parts: (name, polygon (u, v), plane origin, x_dir, z_dir)
# --------------------------------------------------------------------------
def poly_cut(poly, cuts):
    for u0, v0, u1, v1 in cuts:
        poly = poly.difference(Polygon([(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))
    return poly.simplify(1e-6)


def cross_piece(name, x, y0, y1, top, cuts=(), on_rails=False):
    """Piece across the model at x, from y0 to y1; top(y) -> z of its top edge (straight
    pieces between the given break points). Standing on the table (egg-crated into the
    rails), or with on_rails sitting in the rails' top slots (its bottom at their bottom)."""
    base = TABLE + RAIL_H / 2 if on_rails else TABLE
    ys = sorted(set([y0, y1] + [y for y in top.breaks if y0 < y < y1]))
    pts = [(0, 0), (y1 - y0, 0)] + [(y - y0, top(y) - base) for y in reversed(ys)]
    rails = [] if on_rails else [(y - y0 - SLOT / 2, 0, y - y0 + SLOT / 2, RAIL_H / 2) for y in (-RAIL_Y, RAIL_Y)]
    poly = poly_cut(Polygon(pts), rails + [(a - y0, b - base, c - y0, d - base) for a, b, c, d in cuts])
    return (name, poly, (x, y0, base), (0, 1, 0), (1, 0, 0))


class Top:
    """Top edge as z(y) with break points (piecewise straight)."""
    def __init__(self, f, breaks=()):
        self.f, self.breaks = f, list(breaks)

    def __call__(self, y):
        return self.f(y)


def jig_parts(meas, prop, hub):
    st = meas["stick"]
    a = radians(m.THRUST_LEFT)
    rear, across, tips = prop_plate_line(prop, hub, None)
    face = max(tips.values()) + GAP_REF  # the plate's front face, behind the hub along the shaft
    mid = face + T / 2
    o = (hub.X + rear[0] * mid - across[0] * PROP_HALF, hub.Y + rear[1] * mid - across[1] * PROP_HALF)
    w_ang = T / cos(a) + T * tan(a)  # the plate crosses the rails at the side thrust angle
    plate_x = {}  # rail y -> x where the plate crosses it
    plate_cuts = []
    for y in (-RAIL_Y, RAIL_Y):
        u = (y - o[1]) / across[1]
        plate_x[y] = o[0] + across[0] * u
        plate_cuts.append((u - w_ang / 2, 0, u + w_ang / 2, RAIL_H / 2))
    parts = []
    # rails
    xs = [CRADLES_X[0], ref_x(meas, "le"), ref_x(meas, "te"), CRADLES_X[1], meas["stab_le"]["x"], meas["stab_te"]["x"]]
    for name, y in (("kisko vasen", -RAIL_Y), ("kisko oikea", RAIL_Y)):
        # the rails start at the prop plate: in front of it the level blades dip down
        x_front = plate_x[y] - w_ang / 2
        length = X_REAR - x_front
        cuts = [(x - x_front - SLOT / 2, RAIL_H / 2, x - x_front + SLOT / 2, RAIL_H + 1) for x in xs]
        cuts.append((plate_x[y] - x_front - w_ang / 2, RAIL_H / 2, plate_x[y] - x_front + w_ang / 2, RAIL_H + 1))
        poly = poly_cut(Polygon([(0, 0), (length, 0), (length, RAIL_H), (0, RAIL_H)]), cuts)
        parts.append((name, poly, (x_front, y, TABLE), (1, 0, 0), (0, -1, 0)))
    # prop plate: parallel to the prop disc, GAP_REF behind the blade tips; notch for the
    # mount and the stick
    top = hub.Z + PROP_TOP_ABOVE - TABLE
    notch_bottom = meas["mount"].bounding_box().min.Z - NOTCH_BELOW - TABLE
    plate = poly_cut(Polygon([(0, 0), (2 * PROP_HALF, 0), (2 * PROP_HALF, top), (0, top)]),
                     plate_cuts + [(PROP_HALF - PROP_NOTCH, notch_bottom, PROP_HALF + PROP_NOTCH, top + 1)])
    parts.append(("potkurin vertailu", plate, (o[0], o[1], TABLE), across, rear))
    # motor stick cradles
    for name, xc in (("rungon etukannatin", CRADLES_X[0]), ("rungon takakannatin", CRADLES_X[1])):
        zb = stick_bottom(st, xc)
        parts.append(cross_piece(name, xc, -CROSS_W / 2, CROSS_W / 2, Top(lambda y: 0.0),
                                 [(-STICK_SLOT / 2, zb, STICK_SLOT / 2, 1.0)], on_rails=True))
    # wing reference edges: per half the spar bottom line less GAP_REF; notch at the center
    for name, key in (("siiven johtoreunan vertailu", "le"), ("siiven jättöreunan vertailu", "te")):
        fl, fr = meas[key]
        x = ref_x(meas, key)
        zb = stick_bottom(st, x)

        def top_(y, fl=fl, fr=fr):
            f = fl if y < 0 else fr
            return f["k"] * y + f["c"] - GAP_REF
        parts.append(cross_piece(name, x, *meas["tips"][key], Top(top_, [-WING_NOTCH, WING_NOTCH]),
                                 [(-WING_NOTCH, zb - NOTCH_BELOW, WING_NOTCH, 200)]))
    # stab reference edges: one straight tilted line, notch for the stick
    for name, key in (("vakaajan johtoreunan vertailu", "stab_le"), ("vakaajan jättöreunan vertailu", "stab_te")):
        f = meas[key]
        zb = stick_bottom(st, min(f["x"], m.TAIL_END_X - 0.5))
        parts.append(cross_piece(name, f["x"], *meas["tips"][key],
                                 Top(lambda y, f=f: f["k"] * y + f["c"] - GAP_REF, [-STAB_NOTCH, STAB_NOTCH]),
                                 [(-STAB_NOTCH, zb - NOTCH_BELOW, STAB_NOTCH, 200)]))
    return parts, face


# --------------------------------------------------------------------------
def build():
    solids, flat, info = m.build()
    meas = measure(solids)
    prop, hub, fwd = drawing.prop_solid(meas["mount"].bounding_box(), horizontal=True)
    prop.label, prop.color = "potkuri vaaka-asennossa", m.DARK
    parts, face = jig_parts(meas, prop, hub)
    jig = []
    for n, (name, poly, origin, x_dir, z_dir) in enumerate(parts, 1):
        s = wj.solid_of(poly, origin, x_dir, z_dir)
        s.label, s.color = f"{n} {name}", JIG_COLOR
        jig.append(s)
    aircraft = [s for g in solids.values() for s in g]
    return dict(parts=parts, jig=jig, aircraft=aircraft, prop=prop, hub=hub, face=face, meas=meas)


def vol(c):
    return 0 if c is None else (c.volume if hasattr(c, "volume") else sum(x.volume for x in c))


def validate(bld):
    """The whole model on the jig: gaps along every reference edge, incidence, tilt, thrust."""
    jig, meas, n = bld["jig"], bld["meas"], bld["meas"]["names"]
    by = {s.label.split(" ", 1)[1]: s for s in jig}

    def ref_top(piece, y):
        c = piece & (Location((piece.bounding_box().center().X, y, 0)) * Box(50, SLICE, 400))
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
    # side thrust: prop blade tips vs the prop plate's front face (measured on the plate solid)
    plate = by["potkurin vertailu"]
    rear, across, tips = prop_plate_line(bld["prop"], bld["hub"], None)
    hub = bld["hub"]
    for side_, name in ((-1, "vasen"), (1, "oikea")):
        lat = side_ * (m.RULE_PROP_DIA / 2 - 5)
        p = (hub.X + across[0] * lat, hub.Y + across[1] * lat)
        # plate front face along the shaft direction at this tip: nearest plate point behind it
        probe = Location((p[0], p[1], hub.Z)) * Box(0.5, 0.5, 0.5)
        k = 0.0
        while vol(plate.intersect(probe.moved(Location((rear[0] * k, rear[1] * k, 0))))) < 1e-9 and k < 60:
            k += 0.01
        print(f"  {'potkurin vertailu':32s} / lavan kärki {name:6s} {k + 0.25 - tips[side_]:5.2f} mm "
              f"(potkuri vaaka-asennossa)")
    # angles read from the reference edges
    le, te = meas["le"], meas["te"]
    for side_, i in (("vasen", 0), ("oikea", 1)):
        for y in ((-40, -230) if i == 0 else (40, 225)):
            zl, zt = le[i]["k"] * y + le[i]["c"], te[i]["k"] * y + te[i]["c"]
            chord = te[i]["x_rear"] - le[i]["x_front"]  # the spars rest on their outer bottom edges
            inc = degrees(atan((zl - zt) / chord))
            print(f"Asetuskulma {side_} y {y:+5.0f}: {inc:4.2f}° (johto- ja jättöreunan vertailun korkeusero "
                  f"{zl - zt:4.2f} mm, rimojen ulkoreunojen väli {chord:.1f} mm)")
    for key, what in (("le", "siiven johtoreunarima"), ("te", "siiven jättöreunarima"),
                      ("stab_le", "vakaajan johtoreunarima"), ("stab_te", "vakaajan jättöreunarima")):
        ref = by[{"le": "siiven johtoreunan vertailu", "te": "siiven jättöreunan vertailu",
                  "stab_le": "vakaajan johtoreunan vertailu", "stab_te": "vakaajan jättöreunan vertailu"}[key]]
        rb, (yl, yr) = ref.bounding_box(), meas["tips"][key]
        print(f"Kärjet, {what}: vasen {yl:+.1f} / oikea {yr:+.1f} mm keskeltä (vasen {-yl - yr:+.1f} mm pidempi); "
              f"vertailun päät {rb.min.Y:+.1f} / {rb.max.Y:+.1f}")
    s = meas["stab_le"]
    print(f"Vakaajan tiltti: vertailureuna y −120 {s['k'] * -120 + s['c'] - GAP_REF:+.2f}, y +120 "
          f"{s['k'] * 120 + s['c'] - GAP_REF:+.2f} mm (ero {-240 * s['k']:.2f} mm, ±{-120 * s['k']:.2f} mm)")
    print(f"Sivuveto: {m.THRUST_LEFT:g}° vasemmalle (pukki.txt); potkurin vertailu on potkurilevyn suuntainen, "
          f"1 mm ero kärkien raoissa ≈ {degrees(atan(1 / m.RULE_PROP_DIA)):.2f}°")
    # straightness of the model parts themselves (deviation from a straight line)
    print("Mallin rimojen suoruus (poikkeama suorasta): " + ", ".join(
        f"{k} {v:.3f}" for k, v in (("siipi JR v", le[0]["dev"]), ("siipi JR o", le[1]["dev"]), ("siipi JäR v", te[0]["dev"]),
                                     ("siipi JäR o", te[1]["dev"]), ("vakaaja JR", meas["stab_le"]["dev"]),
                                     ("vakaaja JäR", meas["stab_te"]["dev"]))) + " mm")
    # collisions
    jc = Compound(jig)
    hit = {}
    for a_ in bld["aircraft"] + [bld["prop"]]:
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
    src = Path(__file__).name  # shown in the OCP viewer, so it is clear where the model comes from
    jig = Compound(children=bld["jig"], label=f"{src}: tarkastusjigi")
    export_step(jig, STEP_FILE)
    print(f"3D: {STEP_FILE.relative_to(HERE)}")
    if viewer:
        try:
            from ocp_vscode import Camera, show

            plane = Compound(children=bld["aircraft"] + [bld["prop"]], label=f"{src}: lennokki (tarkistus)")
            show(jig, plane, names=[f"{src}: tarkastusjigi", f"{src}: lennokki (tarkistus, p18_iltatahti.py)"],
                 reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Koko lennokin tarkastusjigi 6 mm balsasta")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
