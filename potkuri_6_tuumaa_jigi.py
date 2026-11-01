"""
potkuri_6_tuumaa_jigi.py — an open negative mould for laminating a DIAMETER_IN (7 inch)
propeller, designed with 6propeller.py's method, from 100 g/m2 carbon cloth; the mould is
printed in PLA. The cloth is laid on the lower
mould without pressing: the mould shapes the pressure side, the suction side stays free.
(UPPER = True adds a matching upper half and registration pins for press moulding.)

  cavity        the blades of 6propeller.py's design ("normaali" launch) for a
                DIAMETER_IN prop; no PLA weight limit (the blades are laminated)
  parting       each blade section is split along its pressure side surface (from the
                TE to the LE, then EXT mm on along the chord) and level beyond: the
                lower half shapes the pressure side (and the optional upper half's
                cavity the suction side); the mould comes off straight
  center        a through pocket (2 POCKET_HALF_X along the blades, 2 POCKET_HALF_Y
                across) for the printed four-armed hub cross that takes the shaft and
                the blades' skewers
  spine rod     one straight ROD_D (1 mm) round carbon rod from blade to blade (to ±ROD_REACH
                of the radius), on the blades' upper surface along the blade axis,
                laminated onto it. In the pocket there is nothing else during the lay-up
                (the blades end at the pocket): a ridge across the pocket, from the mould
                bottom, has a snap groove for the rod (center ROD_SNAP under the ridge
                top), so it stays put in the vacuum bag
  skewer slots  only with SKEWER_SLOTS: from the pocket edge SLOT_L mm into each blade
                root, a SKEWER_D snap groove on the pressure side
  split marks   2 x 2 x 2 mm notches in the front edge (-y, top) at x = ±SPLIT_X, where
                the mould can be cut in three
  registration  only with UPPER: pins on the lower half, holes in the upper half
  thickness     at least MIN_T (20 mm) under / over the cavity and the parting surface;
                flat bottom / top for printing, chamfered edges (less warping)
  printing      each half also comes split in three (at x = ±SPLIT_X) with pins and
                holes to join the pieces, for smaller printer beds

Writes (step/): potkuri_6_tuumaa_jigi_ala .step and .stl (one piece) and _ala_1, _ala_2,
_ala_3 .stl (split for printing); with UPPER also the same _yla files.
Run: .venv/bin/python potkuri_6_tuumaa_jigi.py [--no-viewer]
"""

import argparse
import importlib.util
from math import cos, sin
from pathlib import Path

import numpy as np
from build123d import (Align, Axis, Box, Compound, Cylinder, Location, Rot, Solid, Wire, chamfer,
                       export_step, export_stl)

HERE = Path(__file__).parent
OUT = HERE / "step"
NAME = Path(__file__).stem

DIAMETER_IN = 7.0  # prop diameter, inch
POCKET_HALF_X, POCKET_HALF_Y = 17.0, 12.0  # center pocket for the hub cross: 34 x 24 mm, through
SKEWER_SLOTS = False  # 2 mm bamboo skewer slots on the pressure side (replaced by the carbon spine rods)
SKEWER_D, SLOT_L, SNAP = 2.0, 10.0, 0.44  # skewer slots: diameter, length, axis under the surface
ROD_D = 1.0  # carbon spine rod, round
ROD_REACH = 0.5  # rod reaches this fraction of the radius from the center (adjust: e.g. as on Ikara props)
ROD_SNAP = 0.15  # rod center under the ridge top: groove mouth 2 sqrt(r^2 - h^2) = 0.95 mm
RIDGE_W = 4.0  # rod support ridge across the pocket
MARK = 2.0  # split mark notches (cube)
TIP_MARGIN = 15.0  # mould beyond the blade tips
SIDE_MARGIN = 16.0  # mould beside the blades (across)
MIN_T = 20.0  # thinnest mould wall under / over the cavity
EXT = 2.0  # chord line extended beyond the LE / TE before the parting goes level
PIN_D, PIN_H, PIN_CLEAR = 5.0, 6.0, 0.4  # registration pins (lower half) and their holes (upper)
SPLIT_X = 30.0  # print split planes at x = ±SPLIT_X
JOIN_D, JOIN_L, JOIN_CLEAR = 4.0, 8.0, 0.4  # pins joining the printed pieces
EDGE_CHAMFER = 1.0
UPPER = False  # the upper half (press moulding) is not needed: the cloth is laid on, not pressed


def load_prop():
    spec = importlib.util.spec_from_file_location("propeller6", HERE / "6propeller.py")
    p6 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p6)
    p6.use_profile("normaali")
    p6.D = DIAMETER_IN * 25.4e-3
    p6.PROP_MAX_G = 1e9  # laminated carbon blades: the PLA weight limit does not apply
    best, _ = p6.choose()
    prop, info = p6.build(best)
    return p6, prop, best["geom"], best


def parting_points(p6, r, chord, beta, t_max, half_w):
    """Parting line of the section at radius r (blade along +X): level, the pressure side
    surface from the TE to the LE (extended EXT mm along the chord at both ends), level;
    returns [(y, z)] from -half_w to +half_w."""
    cb, sb = cos(beta), sin(beta)
    k = np.linspace(0, np.pi, 24)
    s = (1 - np.cos(k)) / 2  # same stations as 6propeller.section()
    yc = 4 * p6.CAMBER * chord * s * (1 - s)
    naca = 5 * (0.2969 * np.sqrt(s) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1036 * s ** 4) / 0.1
    t = p6.TE_T + (t_max - p6.TE_T) * naca / naca.max()
    lower = []
    for si, y in zip(s[::-1], (yc - t / 2)[::-1]):  # TE -> LE
        u = si * chord - 0.40 * chord
        lower.append((-u * cb - y * sb, -u * sb + y * cb))
    te, le = lower[0], lower[-1]
    te_x = (te[0] - EXT * cb, te[1] - EXT * sb)
    le_x = (le[0] + EXT * cb, le[1] + EXT * sb)
    return [(-half_w, te_x[1]), te_x] + lower + [le_x, (half_w, le_x[1])]


def build():
    p6, prop, geom, best = load_prop()
    R = p6.D / 2 * 1000
    x_end = R + TIP_MARGIN
    half_w = max(0.6 * c * cos(b) + EXT for r, c, b, t in geom if r > POCKET_HALF_X) + SIDE_MARGIN
    # parting stations: from the pocket edge to the tip, then level to the mould end
    rs = [g[0] for g in geom]
    st = [(POCKET_HALF_X, *(float(np.interp(POCKET_HALF_X, rs, [g[i] for g in geom])) for i in (1, 2, 3)))]
    st += [g for g in geom if g[0] > POCKET_HALF_X + 0.5]
    st.append((x_end + 1, *st[-1][1:]))
    lines = [(r, parting_points(p6, r, c, b, t, half_w + 1)) for r, c, b, t in st]
    pb = prop.bounding_box()
    z_lo = min(min(z for _, z in pts) for _, pts in lines + [(0, [(0, pb.min.Z)])])
    z_hi = max(max(z for _, z in pts) for _, pts in lines + [(0, [(0, pb.max.Z)])])
    z_bot, z_top = z_lo - MIN_T, z_hi + MIN_T
    # the space above the parting surface, one blade (+X), lofted from section polygons
    wires = []
    for r, pts in lines:
        poly = [(r, y, z) for y, z in pts] + [(r, half_w + 1, z_top + 1), (r, -half_w - 1, z_top + 1)]
        wires.append(Wire.make_polygon(poly, close=True))
    above = Solid.make_loft(wires, ruled=True)
    above = above + above.rotate(Axis.Z, 180)
    above = above + Location((0, 0, (z_top + 1) / 2)) * Box(2 * POCKET_HALF_X + 0.2, 2 * half_w + 2, z_top + 1)  # center: z 0
    block = Location((0, 0, (z_bot + z_top) / 2)) * Box(2 * x_end, 2 * half_w, z_top - z_bot)
    pocket = Box(2 * POCKET_HALF_X, 2 * POCKET_HALF_Y, 4 * (z_top - z_bot))
    lower = max((block - above - prop - pocket).solids(), key=lambda s: s.volume)
    lower = _chamfer_outer(lower, z_bot)  # before the slots and marks: the chamfer would lose them
    # skewer slots on the blade axis, from the pocket edge into each blade root
    slots = []
    for side in ((1, -1) if SKEWER_SLOTS else ()):
        xa, xb = side * POCKET_HALF_X, side * (POCKET_HALF_X + SLOT_L)
        ends = []
        for x in (xa + side * 0.3, xb):
            # the blade root surface is steep: sink the skewer SNAP mm along the surface
            # normal (into the mould: +y sin(beta), -z cos(beta) for the +X blade)
            beta = float(np.interp(abs(x), rs, [g[2] for g in geom]))
            ends.append((side * SNAP * sin(beta), top_z(lower, x, 0.0) - SNAP * cos(beta)))
        (ya, za), (yb, zb) = ends
        p0 = np.array([xa - side * 1.0, ya, za])
        p1 = np.array([xb, yb, zb])
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        from build123d import Plane
        slot = Plane(origin=tuple(p0), z_dir=tuple(d)).location * Cylinder(SKEWER_D / 2, float(np.linalg.norm(p1 - p0)),
                                                                          align=(Align.CENTER, Align.CENTER, Align.MIN))
        lower = lower - slot
        slots.append((xa, xb, za, zb))
    # spine rod: one straight 1 mm carbon rod from blade to blade over the pocket (the only
    # thing there during the lay-up), on the blades' upper surface along the blade axis; it
    # rests on the surface across its whole width (the root is steep across y). A ridge
    # across the pocket with a snap groove holds it
    r_reach = ROD_REACH * R
    xs = np.linspace(POCKET_HALF_X + 0.5, r_reach, 14)
    ys_ = np.linspace(-ROD_D / 2, ROD_D / 2, 9)
    zc = np.array([max(top_z(prop, x, y) + np.sqrt(max(0.0, (ROD_D / 2) ** 2 - y ** 2)) for y in ys_) for x in xs])
    rod_c = float(zc.max())  # straight and level (both blades are 180 deg symmetric): touches the highest point
    gap_max = float(np.max(rod_c - zc))
    from build123d import Plane as _Pl, Polygon as _Pg, extrude as _ex
    ridge_pts = [(-POCKET_HALF_X, z_bot), (POCKET_HALF_X, z_bot), (POCKET_HALF_X, rod_c + ROD_SNAP),
                 (-POCKET_HALF_X, rod_c + ROD_SNAP)]
    lower = lower + _ex(_Pl.XZ * _Pg(*ridge_pts, align=None), amount=RIDGE_W / 2, both=True)
    lower = lower - Location((0, 0, rod_c)) * Rot(0, 90, 0) * Cylinder(ROD_D / 2, 2 * POCKET_HALF_X)
    rods = [Location((0, 0, rod_c)) * Rot(0, 90, 0) * Cylinder(ROD_D / 2, 2 * r_reach)]
    rod_info = dict(reach=r_reach, length=2 * r_reach, z_center=rod_c, gap_max=gap_max)
    # split marks: 2 mm cubes out of the front edge (-y, top) at x = ±SPLIT_X
    marks = []
    for x in (-SPLIT_X, SPLIT_X):
        zs = top_z(lower, x, -half_w + MARK / 2)
        lower = lower - Location((x, -half_w + MARK / 2, zs - MARK / 2)) * Box(MARK, MARK, MARK)
        marks.append((x, zs))
    lower = max(lower.solids(), key=lambda s: s.volume)
    upper = max(((block & above) - prop - pocket).solids(), key=lambda s: s.volume) if UPPER else None
    if UPPER:  # registration: pins on the lower half's level areas, holes in the upper half
        pin_xy = [(0.0, half_w - 7), (0.0, -half_w + 7), (R + TIP_MARGIN / 2, half_w - 7),
                  (-(R + TIP_MARGIN / 2), -half_w + 7)]
        tip_le_z = lines[-1][1][-1][1]  # level at +y beyond the tip of the +X blade (same at -y for -X)
        for x, y in pin_xy:
            z0 = 0.0 if x == 0 else tip_le_z
            lower = lower + Location((x, y, z0)) * Cylinder(PIN_D / 2, PIN_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
            upper = upper - Location((x, y, z0 - 0.1)) * Cylinder((PIN_D + PIN_CLEAR) / 2, PIN_H + 1.1,
                                                                  align=(Align.CENTER, Align.CENTER, Align.MIN))
        upper = _chamfer_outer(upper, z_top)
        upper.label = f"{Path(__file__).name}: yläpuolisko"
    lower.label = f"{Path(__file__).name}: muotti"
    blades = prop - Box(2 * POCKET_HALF_X, 4 * half_w, 4 * (z_top - z_bot))  # build phase: no hub, blades end at the pocket
    return dict(prop=prop, blades=blades, lower=lower, upper=upper, z_bot=z_bot, z_top=z_top, half_w=half_w, x_end=x_end,
                z_lo=z_lo, z_hi=z_hi, slots=slots, marks=marks, best=best, p6=p6, rods=rods, rod_info=rod_info)


def top_z(solid, x, y):
    """Height of the solid's top surface at (x, y)."""
    c = solid & (Location((x, y, 0)) * Box(0.2, 0.2, 400))
    return c.bounding_box().max.Z


def _chamfer_outer(s, z_flat):
    """Chamfer the edges of the flat printing face (helps against warping and elephant foot)."""
    edges = [e for e in s.edges() if abs(e.center().Z - z_flat) < 1e-3]
    try:
        return chamfer(edges, EDGE_CHAMFER) if edges else s
    except Exception:
        return s


def split3(half, z_mid, outward_pins=True):
    """Split a half at x = ±SPLIT_X; the middle piece gets pins (along X), the outer
    pieces the holes. Returns [left, middle, right]."""
    bb = half.bounding_box()
    big = 4 * max(bb.size.X, bb.size.Y, bb.size.Z)
    left = half & Location((-SPLIT_X - big / 2, 0, 0)) * Box(big, big, big)
    mid = half & Location((0, 0, 0)) * Box(2 * SPLIT_X, big, big)
    right = half & Location((SPLIT_X + big / 2, 0, 0)) * Box(big, big, big)
    hw = bb.size.Y / 2
    for side, outer in ((-1, "left"), (1, "right")):
        for y in (hw - 7, -hw + 7):
            pin = Location((side * SPLIT_X, y, z_mid)) * Rot(0, 90, 0) * Cylinder(JOIN_D / 2, 2 * JOIN_L)
            hole = Location((side * SPLIT_X, y, z_mid)) * Rot(0, 90, 0) * Cylinder((JOIN_D + JOIN_CLEAR) / 2, 2 * JOIN_L + 2)
            mid = mid + (pin & Location((side * (SPLIT_X + JOIN_L / 2), 0, 0)) * Box(JOIN_L, 1000, 1000))
            if outer == "left":
                left = left - hole
            else:
                right = right - hole
    return [max(p.solids(), key=lambda s: s.volume) for p in (left, mid, right)]


def main(viewer=True):
    b = build()
    lo, up = b["lower"], b["upper"]
    best, p6 = b["best"], b["p6"]
    print(f"Potkuri {DIAMETER_IN:g}\" ({p6.D * 1000:.1f} mm): P/D {best['pitch'] / (p6.D * 1000):.2f}, nousu "
          f"{best['pitch']:.0f} mm, matkalento {best['n_c'] * 60:.0f} rpm, hyötysuhde {best['eta_c'] * 100:.0f} %, "
          f"lähdössä suurin kohtauskulma {best['alpha_l']:.1f}°")
    print(f"Muotti {2 * b['x_end']:.0f} × {2 * b['half_w']:.0f} × {lo.bounding_box().size.Z:.1f} mm; "
          f"vähintään {b['z_lo'] - b['z_bot']:.0f} mm muottia pinnan alla; muotoilee lavan painepuolen; "
          f"keskitasku {2 * POCKET_HALF_X:g} × {2 * POCKET_HALF_Y:g} mm")
    for xa, xb, za, zb in b["slots"]:
        print(f"Grillitikun hahlo ⌀{SKEWER_D:g} x {xa:+.0f}…{xb:+.0f} mm (pituus {abs(xb - xa):.0f}), akseli "
              f"{SNAP:g} mm pinnan alla pinnan normaalin suuntaan (suu {2 * (max(0, (SKEWER_D / 2) ** 2 - SNAP ** 2)) ** 0.5:.2f} mm)")
    ri = b["rod_info"]
    print(f"Hiilikuituruoto ⌀{ROD_D:g}, yksi suora {ri['length']:.0f} mm (±{ri['reach']:.0f} mm = ±{ROD_REACH:g} R) "
          f"lapojen yläpinnalla lavan akselilla; lepää pinnalla, rako pintaan enintään {ri['gap_max']:.2f} mm")
    print(f"Kannatusharjanne taskun poikki {RIDGE_W:g} mm leveä; napsautusura ⌀{ROD_D:g}, keskilinja {ROD_SNAP:g} mm "
          f"harjanteen pinnan alla (suu {2 * ((ROD_D / 2) ** 2 - ROD_SNAP ** 2) ** 0.5:.2f} mm), keskellä z {ri['z_center']:+.2f}")
    print("Jakomerkit 2×2×2 mm etureunassa (−y): " + ", ".join(f"x {x:+.0f}" for x, _ in b["marks"]))
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob(f"{NAME}_*"):  # no stale halves or pieces left
        old.unlink()
    files = []
    halves = [("ala", lo, b["z_bot"] + 8)] + ([("yla", up, b["z_top"] - 8)] if up is not None else [])
    for tag, s, _ in halves:
        export_step(s, OUT / f"{NAME}_{tag}.step")
        export_stl(s, str(OUT / f"{NAME}_{tag}.stl"), tolerance=0.02, angular_tolerance=0.1)
        files += [f"{NAME}_{tag}.step", f"{NAME}_{tag}.stl"]
    for tag, s, z_mid in halves:
        for k, piece in enumerate(split3(s, z_mid), 1):
            export_stl(piece, str(OUT / f"{NAME}_{tag}_{k}.stl"), tolerance=0.02, angular_tolerance=0.1)
            files.append(f"{NAME}_{tag}_{k}.stl ({piece.bounding_box().size.X:.0f} mm)")
    print("step/: " + ", ".join(files))
    if viewer:
        try:
            from ocp_vscode import Camera, show

            src = Path(__file__).name
            objs = [lo, b["blades"]] + b["rods"]
            names = [f"{src}: muotti", f"{src}: potkurin lavat rakennusvaiheessa {DIAMETER_IN:g}\"",
                     f"{src}: hiilikuituruoto 1 mm"]
            if up is not None:
                objs.append(up.moved(Location((0, 0, 70))))
                names.append(f"{src}: yläpuolisko (nostettu 70 mm)")
            show(*objs, names=names, colors=(["#c8b28a", "#222222", "#d03030", "#8aa6c8"])[:len(objs)],
                 reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="6\" potkurin laminointimuotti (PLA)")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
