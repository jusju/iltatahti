"""
vasemman_siiven_jigi.py — building jig for the LEFT wing half of the Iltatähti P-18,
cut by laser from one 6 mm balsa board (83 mm wide, 2330 mm long).

The jig is a frame of 6 mm balsa walls standing on edge. The LE and TE walls are
centered under the middle of the LE / TE spar, the root and tip walls lie on the root
and tip of the left wing half; all taken from p18_iltatahti.py with the dihedral laid
flat: the wing is built flat
on the jig, its LE / TE spars resting on the wall tops. The corners are end laps, so
the top is clean. Chordwise braces at the bottom hold the walls square: they sit fully
in notches in the long walls, their ends flush with the wall faces.

Wash-in is built into the jig: the LE wall's top rises evenly from the root to
WASH_IN_LEFT (4 mm) at the tip rib, the tip wall's top falls from the LE to the TE like
the twisted tip rib; the TE and root walls are level.

Holding the parts while the thin CA sets:
  center wall   a spanwise wall under the mid-chord; at every rib 1-5 a fork rises from
                it: a snug RIB_SLOT slot that holds the 2 mm rib upright without pins
  pin lattice   chordwise cross members between the ribs, egg-crated into the LE, TE
                and center walls, flush with the jig top: pins go into their tops and
                into the center wall
  spar fences   low lips at both ends of every cross member, right outside the LE and TE
                spars: they keep the spars in place (not their tilt) without pins

The left wing half is read from p18_iltatahti.py only to place the walls, the wash-in
slope and the forks, and to check that the wing would sit on the jig; it is not part
of the jig's 3D model, the viewer or the laser file.

Writes
  laser/jigi_vasen_siipi1.svg    all jig parts in one laser file (…2.svg if a second
                                 board piece were ever needed); hairline cuts with 1 mm
                                 tabs, engraved part numbers
  step/jigi_vasen_siipi.step     the jig

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

SEVEN_SEGMENT = tl.glyphs  # to_laser's own glyphs; glyphs() below adds letters on top

HERE = Path(__file__).parent
LASER_DIR = HERE / "laser"
STEP_FILE = HERE / "step" / "jigi_vasen_siipi.step"

BOARD_L, BOARD_W, T = 2330.0, 83.0, 6.0  # the 6 mm balsa board (grain along its length)
H = 25.0  # jig height (at least 25)
SLOT = T  # slot width for the 6 mm walls (+0.1 if the board is thicker than nominal)
BRACE_H = 10.0  # chordwise braces at the bottom (as long as the jig is wide)
BRACE_RIBS = (2, 3, 4)  # braces under these ribs (away from the cross members)
RIB_SLOT = 1.9  # fork slot for the 2 mm ribs: the laser kerf opens it to about 2.0, a snug fit
PRONG_W = 4.0  # fork prong width (spanwise) on each side of a rib
GRIP_BELOW_TOP = 0.5  # prongs stop this much below the rib top
CLEAR = 0.3  # prong clearance to other wing parts above it (the center spar at rib 1)
CM_H = 8.0  # cross members (pin lattice): height below the jig top
LIP_W, LIP_H = 3.0, 1.5  # spar fences: width outside the spar, height above the wall top
EDGE, GAP = 3.0, 2.0  # laser: margin to the board edges, gap between parts
JIG_ID = "jigi-vasen-siipi"  # in the file titles and engraved on every part it fits on
# seven segment letters for the engraved id (to_laser has digits only)
LETTERS = {"J": "bcde", "I": "bc", "G": "acdef", "V": "bcdef", "A": "abcefg", "S": "acdfg",
           "E": "adefg", "N": "abcef", "P": "abefg", "-": "g", " ": "", "U": "bcdef", "L": "def",
           "T": "", "K": "", "R": ""}  # T, K, R drawn in glyphs()
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
    """Wall lines from the flat (no wash-in) left half: the middle of the LE spar and of
    the TE spar seen from above (chordwise x), the root and the tip (spanwise y)."""
    bb = Compound(wing).bounding_box()
    mid = {s.label: s.bounding_box().center().X for s in wing if s.label.endswith(("le_spar", "te_spar"))}
    return mid["wing_L_le_spar"], mid["wing_L_te_spar"], bb.max.Y, bb.min.Y


# --------------------------------------------------------------------------
# jig parts: 2D profile (u along the part, v up) + placement
# --------------------------------------------------------------------------
def rect_with_cuts(length, height, cuts, top_end=None):
    """0..length x 0..height (top edge sloping to `top_end` at u = length if given)
    minus axis-parallel rectangles (u0, v0, u1, v1)."""
    poly = Polygon([(0, 0), (length, 0), (length, height if top_end is None else top_end), (0, height)])
    for u0, v0, u1, v1 in cuts:
        poly = poly.difference(Polygon([(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))
    return poly.simplify(1e-6)


def wash_rise(y, root, tip_rib):
    """LE rise of the wing at span position y: 0 at the root, WASH_IN_LEFT at the tip rib."""
    return m.WASH_IN_LEFT * (root - y) / (root - tip_rib)


def rib_holds(wing, x_mid):
    """Ribs 1..5 (the root rib stands on the root wall): (rib, y of its middle, its
    bottom and top in the center wall's thickness, prong tops on the tip / root side)."""
    from build123d import Box, Location

    others = [w for w in wing if not w.label.startswith("wing_L_rib")]
    out = []
    for w in sorted((w for w in wing if w.label.startswith("wing_L_rib") and not w.label.startswith("wing_L_rib0_")),
                    key=lambda w: -w.bounding_box().center().Y):
        b = w.bounding_box()
        cb = (w & (Location((x_mid, b.center().Y, b.center().Z)) * Box(T, 20, 60))).bounding_box()
        yc, bottom, top = cb.center().Y, cb.min.Z, cb.max.Z
        tops = []
        for side in (-1, 1):  # -1: tip side, +1: root side
            ya, yb = sorted((yc + side * RIB_SLOT / 2, yc + side * (RIB_SLOT / 2 + PRONG_W)))
            limit = top - GRIP_BELOW_TOP
            box = Location((x_mid, (ya + yb) / 2, top + 5)) * Box(T, yb - ya, top - bottom + 10 + 10)
            for o in others:
                c = o & box
                if c is not None and c.volume > 1e-6:
                    limit = min(limit, c.bounding_box().min.Z - CLEAR)
            tops.append(max(limit, bottom + 0.5))
        out.append((w.label, yc, bottom, top, tops))
    return out


def wash_rise(y, root, tip_rib):
    """LE rise of the wing at span position y: 0 at the root, WASH_IN_LEFT at the tip rib."""
    return m.WASH_IN_LEFT * (root - y) / (root - tip_rib)


def jig_parts(le, te, out_le, out_te, root, tip, tip_rib, rib_ys, holds):
    """le / te: wall lines under the spar middles; out_le / out_te: the spars' outer
    edges (fences); rib_ys: y of all rib middles (root rib first); holds: rib_holds()."""
    span, chord = root - tip, te - le
    l_long, l_end = span + T, chord + T
    x_mid = (le + te) / 2
    y0 = tip - T / 2  # spanwise walls start here (tip end)
    brace_y = [rib_ys[i] for i in BRACE_RIBS]
    cm_y = [(a + b) / 2 for a, b in zip(rib_ys, rib_ys[1:])]  # cross members between the ribs
    parts = []  # (name, polygon (u, v), plane origin, x_dir, z_dir)

    def spanwise_cuts():
        cuts = [(0, 0, T, H / 2), (l_long - T, 0, l_long, H / 2)]  # end laps from below
        cuts += [(y - y0 - SLOT / 2, 0, y - y0 + SLOT / 2, BRACE_H) for y in brace_y]  # braces sunk in
        cuts += [(y - y0 - SLOT / 2, H - CM_H / 2, y - y0 + SLOT / 2, H + 20) for y in cm_y]  # cross members
        return cuts
    # LE / TE walls: u from the tip end towards the root
    for name, x, wash in (("johtoreunan seinä", le, True), ("jättöreunan seinä", te, False)):
        h0, h1 = (H + wash_rise(y0, root, tip_rib), H + wash_rise(y0 + l_long, root, tip_rib)) if wash else (H, H)
        parts.append((name, rect_with_cuts(l_long, h0, spanwise_cuts(), top_end=h1), (x, y0, -H), (0, 1, 0), (1, 0, 0)))
    # center wall under the mid-chord, with a fork at every rib 1..5
    wall = Polygon([(0, 0), (l_long, 0), (l_long, H), (0, H)])
    for _, yc, bottom, _, (top_tip, top_root) in holds:
        u = yc - y0
        for ua, ub, v in ((u - RIB_SLOT / 2 - PRONG_W, u - RIB_SLOT / 2, top_tip),
                          (u - RIB_SLOT / 2, u + RIB_SLOT / 2, bottom),  # the rib rests on this
                          (u + RIB_SLOT / 2, u + RIB_SLOT / 2 + PRONG_W, top_root)):
            wall = wall.union(Polygon([(ua, 0), (ub, 0), (ub, H + v), (ua, H + v)]))
    wall = wall.intersection(Polygon([(0, 0), (l_long, 0), (l_long, H + 50), (0, H + 50)]))
    for u0, v0, u1, v1 in spanwise_cuts():
        wall = wall.difference(Polygon([(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))
    parts.append(("keskiseinä + haarukat", wall.simplify(1e-6), (x_mid, y0, -H), (0, 1, 0), (1, 0, 0)))
    # root / tip walls: u along the chord from the LE side; end laps and the center wall
    # from above. The tip wall's top falls from the LE wall's height to the TE wall's
    for name, y in (("tyven seinä", root), ("kärjen seinä", tip)):
        r = wash_rise(y, root, tip_rib)
        h0, h1 = H + r * (chord + T / 2) / chord, H - r * (T / 2) / chord  # at u = 0 / u = l_end
        cuts = [(0, H / 2, T, H + 20), (l_end - T, H / 2, l_end, H + 20),
                (x_mid - le + T / 2 - T / 2, H / 2, x_mid - le + T / 2 + T / 2, H + 20)]
        parts.append((name, rect_with_cuts(l_end, h0, cuts, top_end=h1), (le - T / 2, y, -H), (1, 0, 0), (0, -1, 0)))
    # braces: plain strips through the notches of the spanwise walls, ends flush
    for k, y in enumerate(brace_y, 1):
        parts.append((f"tukipala {k}", rect_with_cuts(l_end, BRACE_H, []), (le - T / 2, y, -H), (1, 0, 0), (0, -1, 0)))
    # cross members (pin lattice) with the spar fences at both ends
    x0, x1 = out_le - LIP_W, out_te + LIP_W
    for k, y in enumerate(cm_y, 1):
        r = wash_rise(y, root, tip_rib)
        pts = [(0, 0), (x1 - x0, 0), (x1 - x0, CM_H + LIP_H), (out_te - x0, CM_H + LIP_H), (out_te - x0, CM_H),
               (le + T / 2 - x0, CM_H), (le + T / 2 - x0, CM_H + r), (out_le - x0, CM_H + r),
               (out_le - x0, CM_H + r + LIP_H), (0, CM_H + r + LIP_H)]
        poly = Polygon(pts)
        for x in (le, x_mid, te):
            poly = poly.difference(Polygon([(x - x0 - SLOT / 2, 0), (x - x0 + SLOT / 2, 0),
                                            (x - x0 + SLOT / 2, CM_H / 2), (x - x0 - SLOT / 2, CM_H / 2)]))
        parts.append((f"ristikko {k}", poly.simplify(1e-6), (x0, y, -CM_H), (1, 0, 0), (0, -1, 0)))
    return parts


def solid_of(poly, origin, x_dir, z_dir):
    wire = Wire.make_polygon([(x, y, 0) for x, y in list(poly.exterior.coords)[:-1]], close=True)
    face = Plane(origin=origin, x_dir=x_dir, z_dir=z_dir).location * Face(wire)
    return extrude(face, amount=T / 2, both=True)


# --------------------------------------------------------------------------
# laser file
# --------------------------------------------------------------------------
def laser(parts, stem="jigi_vasen_siipi", jig_id=JIG_ID, what="vasemman siiven jigi") -> list[Path]:
    """Nest the parts on the board (grain = long side along the board) and write one
    SVG per board piece: <stem>1.svg, 2, ...; every part engraved with its number
    and the jig id where it fits."""
    keep = tl.SHEET_L, tl.SHEET_W
    tl.SHEET_L, tl.SHEET_W = BOARD_L, BOARD_W
    for ch, seg in LETTERS.items():
        tl.SEGMENTS.setdefault(ch, seg)
    keep_glyphs = tl.glyphs
    tl.glyphs = glyphs
    try:
        items = [(n, name, tl.normalize(poly)) for n, (name, poly, *_) in enumerate(parts, 1)]
        sheets = tl.nest(items, edge=EDGE, gap=GAP)
        tl.TAB_COUNT.clear()
        files = []
        for i, sheet in enumerate(sheets, 1):
            used = math.ceil(max(p.bounds[2] for _, _, p in sheet.placed) + EDGE)
            cut, engrave = [], []
            for num, name, poly in sheet.placed:
                cut.append(f'    <g id="{jig_id}-osa{num}"><title>{jig_id} {num}: {name}</title>')
                for c in tl.cut_paths_with_tabs(poly):
                    cut.append(f'      <path style="{tl.CUT_STYLE}" d="{svg_d(c)}"/>')
                cut.append("    </g>")
                lab = tl.label_for(poly, f"{num} {jig_id.upper()}") or tl.label_for(poly, str(num))
                if lab is not None:
                    d = " ".join(svg_d(r.coords, True) for g in getattr(lab, "geoms", [lab])
                                 for r in (g.exterior, *g.interiors))
                    engrave.append(f'    <path style="{tl.ENGRAVE_STYLE}" d="{d}"><title>{num}</title></path>')
            path = LASER_DIR / f"{stem}{i}.svg"
            path.write_text("\n".join([
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                f'width="{used}mm" height="{BOARD_W:g}mm" viewBox="0 0 {used} {BOARD_W:g}">',
                f"  <title>{jig_id} {i}: {what}, balsa {T:g} mm, pala {used} × {BOARD_W:g} mm</title>",
                f"  <desc>{jig_id}: Iltatähti P-18, {what}, {len(sheet.placed)} osaa</desc>",
                '  <g id="engrave" inkscape:groupmode="layer" inkscape:label="kaiverrus">', *engrave, "  </g>",
                '  <g id="cut" inkscape:groupmode="layer" inkscape:label="leikkaus">', *cut, "  </g>",
                "</svg>"]) + "\n")
            files.append((path, used, sheet))
        return files
    finally:
        tl.SHEET_L, tl.SHEET_W = keep
        tl.glyphs = keep_glyphs


def glyphs(text, h):
    """to_laser's seven segment glyphs, plus a real V and a centered I for the id text."""
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union

    w, st, gap = 0.6 * h, 0.16 * h, 0.22 * h
    shapes = []
    for i, ch in enumerate(text):
        x = i * (w + gap)
        if ch == "V":
            v = LineString([(st / 2, h), (w / 2, st / 2), (w - st / 2, h)]).buffer(st / 2, cap_style=2, join_style=2)
            shapes.append(affinity.translate(v.intersection(box(0, 0, w, h)), x, 0))
        elif ch == "I":
            shapes.append(box(x + (w - st) / 2, 0, x + (w + st) / 2, h))
        elif ch == "T":
            shapes += [box(x, h - st, x + w, h), box(x + (w - st) / 2, 0, x + (w + st) / 2, h)]
        elif ch in "KR":
            stem_ = box(x, 0, x + st, h)
            if ch == "K":
                legs = LineString([(w, h), (st, h / 2), (w, 0)]).buffer(st / 2, cap_style=2, join_style=2)
            else:
                legs = unary_union([affinity.translate(SEVEN_SEGMENT("P", h), 0, 0),
                                    LineString([(w / 2, h / 2), (w - st / 2, 0)]).buffer(st / 2, cap_style=2)])
            shapes += [stem_, affinity.translate(legs.intersection(box(0, 0, w, h)), x, 0)]
        elif ch != " ":
            shapes.append(affinity.translate(SEVEN_SEGMENT(ch, h), x, 0))
    return unary_union(shapes)


def svg_d(coords, closed=False):
    pts = [f"{x:.3f},{BOARD_W - y:.3f}" for x, y in coords]
    return "M " + " L ".join(pts) + (" Z" if closed else "")


# --------------------------------------------------------------------------
def build():
    """The jig and the wing copy on it: dict with parts (name, polygon, placement),
    solids (jig, in the parts' order), wing (copy on the jig) and the lines used."""
    flat_wing = left_wing(wash_in=False)
    le, te, root, tip = outline(flat_wing)
    tip_rib = max((s for s in flat_wing if s.label.startswith("wing_L_rib")),
                  key=lambda s: -s.bounding_box().center().Y).bounding_box().center().Y
    # the LE / TE spar outer bottom edges are the lowest points (0.17 below the rib
    # ends, the spars lie on the sloping rib tabs): the wing rests on them
    lift = -Compound(flat_wing).bounding_box().min.Z
    wing = on_jig(left_wing(wash_in=True), lift)
    fb = Compound(flat_wing).bounding_box()
    rib_ys = sorted((w.bounding_box().center().Y for w in wing if w.label.startswith("wing_L_rib")), reverse=True)
    holds = rib_holds(wing, (le + te) / 2)
    parts = jig_parts(le, te, fb.min.X, fb.max.X, root, tip, tip_rib, rib_ys, holds)
    solids = []
    for n, (name, poly, origin, x_dir, z_dir) in enumerate(parts, 1):
        s = solid_of(poly, origin, x_dir, z_dir)
        s.label, s.color = f"{n} {name}", JIG_COLOR
        solids.append(s)
    return dict(parts=parts, solids=solids, wing=wing, flat_wing=flat_wing, le=le, te=te, root=root, tip=tip,
                tip_rib=tip_rib, holds=holds)


def main(viewer=True):
    b = build()
    parts, solids, wing, flat_wing, holds = b["parts"], b["solids"], b["wing"], b["flat_wing"], b["holds"]
    le, te, root, tip, tip_rib = b["le"], b["te"], b["root"], b["tip"], b["tip_rib"]

    fb = Compound(flat_wing).bounding_box()
    print(f"Vasen siipi (V-kulma oiottu): ääriviiva x {fb.min.X:.2f} ... {fb.max.X:.2f}, y {tip:.2f} ... {root:.2f}")
    print(f"Seinien keskiviivat: johtoreunariman keskellä x {le:.2f}, jättöreunariman keskellä x {te:.2f} "
          f"(väli {te - le:.2f} mm), tyvi y {root:.2f}, kärki y {tip:.2f}; jigi {te - le + T:.1f} × "
          f"{root - tip + T:.1f} mm, korkeus {H:g} mm")
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
    hit = press = 0.0
    jig_c = Compound(solids)
    for w_ in wing:
        c = w_.intersect(jig_c)
        v = 0 if c is None else (c.volume if hasattr(c, "volume") else sum(x.volume for x in c))
        if w_.label.startswith("wing_L_rib"):
            press += v  # the forks grip the ribs: RIB_SLOT is narrower than the rib
        else:
            hit += v
    print("Haarukat (keskiseinä, x {:.1f}): ".format((le + te) / 2) + "; ".join(
        f"{lab.split('_')[2]}: pohja z {bot:+.2f}, piikit {tt:+.2f}/{tr:+.2f} (kaaren yläreuna {top:+.2f})"
        for lab, _, bot, top, (tt, tr) in holds))
    print(f"Kaarien puristus haarukoissa {press:.2f} mm³ (rako {RIB_SLOT:g} mm, kaari 2 mm)")
    le_sp = next(w_ for w_ in wing if w_.label == "wing_L_le_spar")
    near = [v for v in le_sp.vertices() if abs(v.Y - tip_rib) < 3]
    low_le = min(v.Z for v in near) if near else float("nan")
    print(f"Wash-in: johtoreunan seinä nousee tyvestä kärkikaareen (y {tip_rib:.1f}) "
          f"{wash_rise(tip_rib, root, tip_rib):.2f} mm; siiven johtoreunarima kärkikaaren kohdalla "
          f"z {low_le:+.2f} mm (seinän yläreuna {wash_rise(tip_rib, root, tip_rib):+.2f}); "
          f"siipi ja jigi päällekkäin {hit:.3f} mm³")
    print(f"Tarkistus, siipi jigin päällä: alin kohta z {wb.min.Z:+.2f} mm (jigin yläpinta z 0, "
          f"johto- ja jättöreunarimat yläpintaa vasten; vasen kärki nousee wash-inin verran)")

    LASER_DIR.mkdir(exist_ok=True)
    files = laser(parts)
    print("\nOsat:")
    for n, (name, poly, *_) in enumerate(parts, 1):
        b = poly.bounds
        print(f"  {n:2d}  {name:22s} {b[2] - b[0]:6.1f} × {b[3] - b[1]:4.1f} mm")
    for path, used, sheet in files:
        print(f"\nLaser: {path.relative_to(HERE)}: {len(sheet.placed)} osaa, balsaa tarvitaan "
              f"{used} mm × {BOARD_W:g} mm × {T:g} mm (laudasta {BOARD_L:g} mm jää {BOARD_L - used:g} mm)")
    print(f"Sillat (1 mm): vähintään {min(tl.TAB_COUNT)} / osa")

    STEP_FILE.parent.mkdir(exist_ok=True)
    jig = Compound(children=solids, label="jigi_vasen_siipi")
    export_step(jig, STEP_FILE)
    print(f"3D: {STEP_FILE.relative_to(HERE)}")
    if viewer:
        try:
            from ocp_vscode import Camera, show

            show(jig, names=["jigi"], reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Vasemman siiven rakennusjigi 6 mm balsasta")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
