"""
vasemman_siiven_jigi.py — building jig for the LEFT wing half of the Iltatähti P-18,
cut by laser from one 6 mm balsa board (83 mm wide, 2330 mm long).

The jig is a frame of 6 mm balsa walls standing on edge. The middle of every wall
lies exactly on the outline of the left wing half (leading edge, trailing edge, root,
tip), taken from p18_iltatahti.py with the dihedral laid flat: the wing is built flat
on the jig, its rib ends resting on the wall tops. The corners are end laps, so the
top is flat and clean. Chordwise braces at the bottom hold the walls square: egg-crate
slots, the brace tops stay well below the jig top.

A copy of the left wing half (as modelled, wash-in included) is placed on the jig in
the OCP CAD Viewer to check that the walls are where they should be.

Writes
  laser/jigi_vasen_siipi1.svg    all jig parts in one laser file (…2.svg if a second
                                 board piece were ever needed); hairline cuts with 1 mm
                                 tabs, engraved part numbers
  step/jigi_vasen_siipi.step     jig + the wing copy

Run:  .venv/bin/python vasemman_siiven_jigi.py [--no-viewer]
"""

import argparse
import math
from pathlib import Path

from build123d import Axis, Compound, Face, Plane, Wire, export_step, extrude
from shapely import affinity
from shapely.geometry import Polygon

import p18_iltatahti as m
import to_laser as tl

HERE = Path(__file__).parent
LASER_DIR = HERE / "laser"
STEP_FILE = HERE / "step" / "jigi_vasen_siipi.step"

BOARD_L, BOARD_W, T = 2330.0, 83.0, 6.0  # the 6 mm balsa board (grain along its length)
H = 25.0  # jig height (at least 25)
SLOT = T  # slot width for the 6 mm walls (+0.1 if the board is thicker than nominal)
BRACE_L, BRACE_H = 100.0, 10.0  # chordwise braces at the bottom
BRACE_AT = (0.25, 0.5, 0.75)  # brace places along the span, root 0 ... tip 1
EDGE, GAP = 3.0, 2.0  # laser: margin to the board edges, gap between parts
JIG_COLOR = m.Color(0.55, 0.40, 0.25)


# --------------------------------------------------------------------------
# the left wing half, dihedral laid flat (wing frame: x chord from the LE, y span,
# rib end bottoms at z = 0)
# --------------------------------------------------------------------------
def left_wing(wash_in=True):
    keep = m.WASH_IN_LEFT
    if not wash_in:
        m.WASH_IN_LEFT = 0.0
    try:
        parts, _, _, dih = m.wing_parts()
    finally:
        m.WASH_IN_LEFT = keep
    out = []
    for p in parts:
        if not p.name.startswith("wing_L_") or "_leg_" in p.name:
            continue  # the saddle legs hang below the wing, not part of the jig check
        s = p.solid().rotate(Axis.X, dih)  # left half: spar direction (0, -cos, sin) -> (0, -1, 0)
        s.label, s.color = p.name, m.BALSA
        out.append(s)
    return out


def on_jig(wing, lift):
    """Move the wing copy up so it rests on the jig top (z 0) with its lowest points."""
    from build123d import Location
    out = []
    for s in wing:
        t = s.moved(Location((0, 0, lift)))
        t.label, t.color = s.label, s.color
        out.append(t)
    return out


def outline(wing):
    """Planform outline of the flat (no wash-in) left half: LE x, TE x, root y, tip y."""
    bb = Compound(wing).bounding_box()
    return bb.min.X, bb.max.X, bb.max.Y, bb.min.Y


# --------------------------------------------------------------------------
# jig parts: 2D profile (u along the part, v up) + placement
# --------------------------------------------------------------------------
def rect_with_cuts(length, height, cuts):
    """Rectangle 0..length x 0..height minus axis-parallel rectangles (u0, v0, u1, v1)."""
    poly = Polygon([(0, 0), (length, 0), (length, height), (0, height)])
    for u0, v0, u1, v1 in cuts:
        poly = poly.difference(Polygon([(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))
    return poly.simplify(1e-6)


def jig_parts(le, te, root, tip):
    span, chord = root - tip, te - le
    l_long, l_end = span + T, chord + T
    brace_y = [root - f * span for f in BRACE_AT]
    xb0 = (le + te) / 2 - BRACE_L / 2  # brace start (chordwise)
    parts = []  # (name, polygon (u, v), plane origin, x_dir, z_dir)
    # LE / TE walls: u from the tip end towards the root; end laps from below at both
    # ends, brace slots from below
    for name, x in (("johtoreunan seinä", le), ("jättöreunan seinä", te)):
        cuts = [(0, 0, T, H / 2), (l_long - T, 0, l_long, H / 2)]
        for y in brace_y:
            u = y - (tip - T / 2)
            cuts.append((u - SLOT / 2, 0, u + SLOT / 2, BRACE_H / 2))
        parts.append((name, rect_with_cuts(l_long, H, cuts), (x, tip - T / 2, -H), (0, 1, 0), (1, 0, 0)))
    # root / tip walls: u along the chord from the LE side; end laps from above
    for name, y in (("tyven seinä", root), ("kärjen seinä", tip)):
        cuts = [(0, H / 2, T, H), (l_end - T, H / 2, l_end, H)]
        parts.append((name, rect_with_cuts(l_end, H, cuts), (le - T / 2, y, -H), (1, 0, 0), (0, -1, 0)))
    # braces: slots from above where the LE / TE walls cross
    for k, y in enumerate(brace_y, 1):
        cuts = [(x - xb0 - SLOT / 2, BRACE_H / 2, x - xb0 + SLOT / 2, BRACE_H) for x in (le, te)]
        parts.append((f"tukipala {k}", rect_with_cuts(BRACE_L, BRACE_H, cuts), (xb0, y, -H), (1, 0, 0), (0, -1, 0)))
    return parts


def solid_of(poly, origin, x_dir, z_dir):
    wire = Wire.make_polygon([(x, y, 0) for x, y in list(poly.exterior.coords)[:-1]], close=True)
    face = Plane(origin=origin, x_dir=x_dir, z_dir=z_dir).location * Face(wire)
    return extrude(face, amount=T / 2, both=True)


# --------------------------------------------------------------------------
# laser file
# --------------------------------------------------------------------------
def laser(parts) -> list[Path]:
    """Nest the parts on the board (grain = long side along the board) and write one
    SVG per board piece: jigi_vasen_siipi1.svg, 2, ..."""
    keep = tl.SHEET_L, tl.SHEET_W
    tl.SHEET_L, tl.SHEET_W = BOARD_L, BOARD_W
    try:
        items = [(n, name, tl.normalize(poly)) for n, (name, poly, *_) in enumerate(parts, 1)]
        sheets = tl.nest(items, edge=EDGE, gap=GAP)
        tl.TAB_COUNT.clear()
        files = []
        for i, sheet in enumerate(sheets, 1):
            used = math.ceil(max(p.bounds[2] for _, _, p in sheet.placed) + EDGE)
            cut, engrave = [], []
            for num, name, poly in sheet.placed:
                cut.append(f'    <g id="osa{num}"><title>{num}: {name}</title>')
                for c in tl.cut_paths_with_tabs(poly):
                    cut.append(f'      <path style="{tl.CUT_STYLE}" d="{svg_d(c)}"/>')
                cut.append("    </g>")
                lab = tl.label_for(poly, str(num))
                if lab is not None:
                    d = " ".join(svg_d(r.coords, True) for g in getattr(lab, "geoms", [lab])
                                 for r in (g.exterior, *g.interiors))
                    engrave.append(f'    <path style="{tl.ENGRAVE_STYLE}" d="{d}"><title>{num}</title></path>')
            path = LASER_DIR / f"jigi_vasen_siipi{i}.svg"
            path.write_text("\n".join([
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                f'width="{used}mm" height="{BOARD_W:g}mm" viewBox="0 0 {used} {BOARD_W:g}">',
                f"  <title>Vasemman siiven jigi {i}: balsa {T:g} mm, pala {used} × {BOARD_W:g} mm</title>",
                '  <g id="engrave" inkscape:groupmode="layer" inkscape:label="kaiverrus">', *engrave, "  </g>",
                '  <g id="cut" inkscape:groupmode="layer" inkscape:label="leikkaus">', *cut, "  </g>",
                "</svg>"]) + "\n")
            files.append((path, used, sheet))
        return files
    finally:
        tl.SHEET_L, tl.SHEET_W = keep


def svg_d(coords, closed=False):
    pts = [f"{x:.3f},{BOARD_W - y:.3f}" for x, y in coords]
    return "M " + " L ".join(pts) + (" Z" if closed else "")


# --------------------------------------------------------------------------
def main(viewer=True):
    flat_wing = left_wing(wash_in=False)
    le, te, root, tip = outline(flat_wing)
    # the LE / TE spar outer bottom edges are the lowest points (0.17 below the rib
    # ends, the spars lie on the sloping rib tabs): the wing rests on them
    lift = -Compound(flat_wing).bounding_box().min.Z
    wing = on_jig(left_wing(wash_in=True), lift)
    parts = jig_parts(le, te, root, tip)
    solids = []
    for n, (name, poly, origin, x_dir, z_dir) in enumerate(parts, 1):
        s = solid_of(poly, origin, x_dir, z_dir)
        s.label, s.color = f"{n} {name}", JIG_COLOR
        solids.append(s)

    print(f"Vasemman siiven ääriviiva (V-kulma oiottu): johtoreuna x {le:.2f}, jättöreuna x {te:.2f}, "
          f"tyvi y {root:.2f}, kärki y {tip:.2f}  ->  {te - le:.1f} × {root - tip:.1f} mm")
    print(f"Jigin seinien keskiviivat ovat näillä viivoilla; jigi {te - le + T:.0f} × {root - tip + T:.0f} mm, "
          f"korkeus {H:g} mm")
    # checks: jig parts must not overlap each other; the wing must sit on the jig top
    over = []
    for i, a in enumerate(solids):
        for b in solids[i + 1:]:
            c = a.intersect(b)
            v = 0 if c is None else (c.volume if hasattr(c, "volume") else sum(x.volume for x in c))
            if v > 0.01:
                over.append((a.label, b.label, v))
    print("Jigin osat: " + ("ei päällekkäisyyksiä" if not over else
                            "PÄÄLLEKKÄIN " + ", ".join(f"{a} / {b} {v:.2f} mm³" for a, b, v in over)))
    wb = Compound(wing).bounding_box()
    print(f"Siiven kopio jigin päällä: alin kohta z {wb.min.Z:+.2f} mm (jigin yläpinta z 0, "
          f"johto- ja jättöreunarimat yläpintaa vasten; vasen kärki nousee wash-inin verran)")

    LASER_DIR.mkdir(exist_ok=True)
    files = laser(parts)
    print("\nOsat:")
    for n, (name, poly, *_) in enumerate(parts, 1):
        b = poly.bounds
        print(f"  {n}  {name:20s} {b[2] - b[0]:6.1f} × {b[3] - b[1]:4.1f} mm")
    for path, used, sheet in files:
        print(f"\nLaser: {path.relative_to(HERE)}: {len(sheet.placed)} osaa, balsaa tarvitaan "
              f"{used} mm × {BOARD_W:g} mm × {T:g} mm (laudasta {BOARD_L:g} mm jää {BOARD_L - used:g} mm)")
    print(f"Sillat (1 mm): vähintään {min(tl.TAB_COUNT)} / osa")

    STEP_FILE.parent.mkdir(exist_ok=True)
    jig = Compound(children=solids, label="jigi_vasen_siipi")
    wing_c = Compound(children=wing, label="vasen_siipi (kopio)")
    export_step(Compound(children=[jig, wing_c], label="jigi + vasen siipi"), STEP_FILE)
    print(f"3D: {STEP_FILE.relative_to(HERE)}")
    if viewer:
        try:
            from ocp_vscode import Camera, show

            show(jig, wing_c, names=["jigi", "vasen siipi (kopio)"], reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Vasemman siiven rakennusjigi 6 mm balsasta")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
