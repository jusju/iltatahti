"""
readme_assets.py — pictures and generated tables for README.md, from the same model.

Writes
  docs/iltatahti_3d.svg          rotating 3D model (animated SVG, plays on GitHub)
  docs/iltatahti_iso.svg         the 3D view at the top of the building drawing (hidden edges dashed)
  docs/rakennuspiirustus.png     the A0 building drawing as a picture
  step/iltatahti_p18.stl         whole model as STL (GitHub shows it in an interactive 3D viewer)
and fills the generated blocks of README.md (between <!-- BEGIN:x --> and <!-- END:x -->):
  tekniset   key data
  saannot    P-18 rule check
  paino      weight budget part by part (target 7.5 g without rubber)

Run after the model has changed (sync_all.py first, so the drawing PDF is current):
  .venv/bin/python readme_assets.py
"""

import dataclasses
import re
import subprocess
from math import cos, radians, sin
from pathlib import Path

from build123d import Compound, Face, GeomType, Location, Wire, export_stl
from shapely.geometry import LineString

import drawing
import p18_iltatahti as m

HERE = Path(__file__).parent
DOCS = HERE / "docs"
README = HERE / "README.md"

# weight budget assumptions
BALSA_NOMINAL, BALSA_MAX = 65.0, 70.0  # kg/m³: expected, and the budget (heaviest allowed sheet)
PETG = 1.27  # g/cm³, printed solid
STEEL = 7.85  # g/cm³, music wire
CARBON = 1.6  # g/cm³, pultruded strip
MYLAR = 1.39 * 2e-3 * 1e-1  # g/cm² for 2 µm film (1.39 g/cm³)
COVER_EXTRA = 1.10  # +10 % for overlaps around the frame
TARGET = 7.5  # g without rubber (P-18 rule 8: the minimum)
SHAFT_D, SHAFT_L = 1.0, 45.0  # mm prop shaft wire: through the bearing to the front hook
HOOK_D, HOOK_L = 0.8, 40.0  # mm rear hook
PROP_BUDGET = 2.5  # g, 6" STEM plastic prop without its hanger (weigh it!)
CF_T, CF_W = 0.1, 1.0  # mm carbon strips on the stick top and bottom


def fi(v: float, dec: int = 3) -> str:
    return f"{v:.{dec}f}".replace(".", ",")


def wire_g(d, length):
    return 3.14159265 * (d / 2) ** 2 * length / 1000 * STEEL


# --------------------------------------------------------------------------
# part names (Finnish), one row per laser part
# --------------------------------------------------------------------------
def part_name(n: str) -> str:
    side = {"L": "vasen siipi", "R": "oikea siipi"}
    if n.startswith("wing_") and n != "wing_wedge":
        s = side[n.split("_")[1]]
        if n.endswith("le_spar"):
            return f"{s}: etureunarima"
        if n.endswith("te_spar"):
            return f"{s}: jättöreunarima"
        if n.endswith("center_spar"):
            return f"{s}: V-kulman keskirima"
        if "_rib" in n:
            k = int(n.split("_rib")[1].split("_")[0])
            kind = ["tyvikaari", "täysikaari (keskiriman lovi)"][k] if k < 2 else f"siipikaari {k}"
            return f"{s}: {kind}"
        if "leg_front" in n:
            return f"{s}: satulan etutuki"
        if "leg_rear" in n:
            return f"{s}: satulan takatuki"
    if n.startswith("stab_le"):
        return "korkeusvakaaja: etureunarima"
    if n.startswith("stab_te"):
        return "korkeusvakaaja: jättöreunarima"
    if n.startswith("stab_rib"):
        i = int(n[len("stab_rib"):])
        place, w = m.STAB_RIBS[i]
        where = {-1.0: "vasen kärki", -0.5: "vasen puoliväli", 0.0: "keskellä", 0.5: "oikea puoliväli",
                 1.0: "oikea kärki"}.get(place, f"{place:+g}")
        return f"korkeusvakaaja: kaari, {where}"
    return {"fin_le": "sivuperäsin: johtoreuna + sarana-akseli", "fin_root": "sivuperäsin: alarima",
            "fin_top": "sivuperäsin: ylärima", "fin_te": "sivuperäsin: jättöreuna",
            "motor_stick": "runkotikku", "wing_wedge": "kohtauskulmakiila 2°"}.get(n, n)


def group_of(n: str) -> str:
    if n.startswith("wing_L"):
        return "Vasen siipi"
    if n.startswith("wing_R"):
        return "Oikea siipi"
    if n.startswith("stab"):
        return "Korkeusvakaaja"
    if n.startswith("fin"):
        return "Sivuperäsin"
    return "Runko"


# --------------------------------------------------------------------------
# weight budget
# --------------------------------------------------------------------------
def budget(solids, flat, info):
    rows, groups = [], {}
    for num, p in enumerate(flat, 1):
        b = p.profile.bounding_box()
        vol = p.profile.area * p.thickness  # mm³, exact for a flat part
        g = group_of(p.name)
        r = (str(num), part_name(p.name), f"{fi(b.size.X, 1)}×{fi(b.size.Y, 1)}×{fi(p.thickness, 0)}",
             vol, vol * BALSA_NOMINAL * 1e-6, vol * BALSA_MAX * 1e-6, g)
        rows.append(r)
        groups.setdefault(g, []).append(r)

    mount = next(s for s in solids["hardware"] if s.label == "pukki")
    spans, chord = info["spans"], info["chord"]
    stab_bb = Compound(solids["stab"]).bounding_box()
    wing_a = (spans["L"] + spans["R"]) * chord / 100  # cm²
    stab_a = stab_bb.size.Y * info["stab_chord"] / 100
    fin_a = (m.RUDDER_ROOT + m.RUDDER_TIP) / 2 * m.RUDDER_HEIGHT / 100
    cf = CF_T * CF_W * m.STICK_LEN / 1000 * CARBON

    n0 = len(flat)  # parts list numbers after the laser parts: mount, rear hook, prop (as in the drawing)
    # (number, name, basis, grams); all budget values (max), estimates marked
    extra = {
        "Vasen siipi": [("", "kalvo mylar 2 µm, vasen puolisko", f"{fi(wing_a * spans['L'] / (spans['L'] + spans['R']), 0)} cm² +10 %",
                         wing_a * spans["L"] / (spans["L"] + spans["R"]) * MYLAR * COVER_EXTRA),
                        ("", "liimat (kaaret, rimat, tuet) ja 3M77", "arvio", 0.060)],
        "Oikea siipi": [("", "kalvo mylar 2 µm, oikea puolisko", f"{fi(wing_a * spans['R'] / (spans['L'] + spans['R']), 0)} cm² +10 %",
                         wing_a * spans["R"] / (spans["L"] + spans["R"]) * MYLAR * COVER_EXTRA),
                        ("", "liimat (kaaret, rimat, tuet) ja 3M77", "arvio", 0.060)],
        "Korkeusvakaaja": [("", "kalvo mylar 2 µm", f"{fi(stab_a, 0)} cm² +10 %", stab_a * MYLAR * COVER_EXTRA),
                           ("", "liimat ja 3M77", "arvio", 0.030)],
        "Sivuperäsin": [("", "kalvo mylar 2 µm", f"{fi(fin_a, 0)} cm² +10 %", fin_a * MYLAR * COVER_EXTRA),
                        ("", "liimat, S-saumat ja 3M77", "arvio", 0.015),
                        ("", "saranan mehupilli (pahvi, ~25 mm) + karhulanka + CA", "arvio", 0.080)],
        "Runko": [("", "hiilikuitulatta tikun päällä", f"{fi(CF_T, 1)}×{fi(CF_W, 0)}×{fi(m.STICK_LEN, 0)} mm, {fi(CARBON, 1)} g/cm³", cf),
                  ("", "hiilikuitulatta tikun alla", f"{fi(CF_T, 1)}×{fi(CF_W, 0)}×{fi(m.STICK_LEN, 0)} mm, {fi(CARBON, 1)} g/cm³", cf),
                  ("", "CA-liima latoille", "arvio", 0.030),
                  ("", "liimat: kiila, satulan tuet tikkuun, pukki", "arvio", 0.030)],
        "Moottoripukki ja potkuri": [
            (str(n0 + 1), "moottoripukki PETG (pukki.py)", f"{fi(mount.volume, 0)} mm³ umpinainen, {fi(PETG, 2)} g/cm³", mount.volume / 1000 * PETG),
            ("", "potkurin akseli, pianolanka", f"⌀{fi(SHAFT_D, 1)} × {fi(SHAFT_L, 0)} mm", wire_g(SHAFT_D, SHAFT_L)),
            ("", "2 lasihelmeä", "arvio", 0.030),
            ("", "3 mylar-prikkaa + teflonöljy", "arvio", 0.010),
            (str(n0 + 3), "potkuri 6\" (STEM, ilman ripustinta)", "arvio — punnitse", PROP_BUDGET)],
        "Takakoukku": [(str(n0 + 2), "takakumikoukku, pianolanka", f"⌀{fi(HOOK_D, 1)} × {fi(HOOK_L, 0)} mm", wire_g(HOOK_D, HOOK_L)),
                       ("", "karhulankasidonta + CA", "arvio", 0.020)],
    }
    return rows, groups, extra


def budget_md(rows, groups, extra) -> str:
    out = [f"Balsaosien budjetti on laskettu {fi(BALSA_MAX, 0)} kg/m³:n balsalle (raskain sallittu levy): "
           "laserosan pinta-ala × levyn paksuus mallista. Arvio-rivit ovat kokemusperäisiä ylärajoja.", ""]
    total = 0.0
    order = ["Vasen siipi", "Oikea siipi", "Korkeusvakaaja", "Sivuperäsin", "Runko",
             "Moottoripukki ja potkuri", "Takakoukku"]
    summary = []
    for g in order:
        out += [f"#### {g}", "", "| Osa | Nimi | Mitat mm | Budjetti g |", "|---:|---|---|---:|"]
        sb = 0.0
        for num, name, size, _vol, _gn, gb, _ in groups.get(g, []):
            out.append(f"| {num} | {name} | {size} | {fi(gb)} |")
            sb += gb
        for num, name, basis, grams in extra.get(g, []):
            out.append(f"| {num} | {name} | {basis} | {fi(grams)} |")
            sb += grams
        out += [f"| | **{g} yhteensä** | | **{fi(sb)}** |", ""]
        summary.append((g, sb))
        total += sb
    out += ["#### Yhteenveto", "", "| Ryhmä | Budjetti g |", "|---|---:|"]
    out += [f"| {g} | {fi(b)} |" for g, b in summary]
    out += [f"| **Yhteensä ilman kumia** | **{fi(total)}** |",
            f"| Varaus / painotus 7,5 g:aan | {fi(TARGET - total)} |",
            f"| **Tavoite (P-18 sääntö 8)** | **{fi(TARGET, 1)}** |", ""]
    out += [f"Balsaa yhteensä enintään {fi(sum(r[5] for r in rows), 2)} g. Kumimoottori ei kuulu painoon."]
    return "\n".join(out)


# --------------------------------------------------------------------------
# key data and rule check
# --------------------------------------------------------------------------
def rule_rows(solids):
    def bb(group):
        return Compound(solids[group]).bounding_box()
    w, s = bb("wing"), bb("stab")
    allbb = Compound([x for g in solids.values() for x in g]).bounding_box()
    return [("siiven kärkiväli (projektio)", w.size.Y, m.RULE_WING_SPAN, "3"),
            ("siiven jänne (projektio)", w.size.X, m.RULE_WING_CHORD, "3"),
            ("korkeusvakaajan kärkiväli", s.size.Y, m.RULE_STAB_SPAN, "4"),
            ("korkeusvakaajan jänne", s.size.X, m.RULE_STAB_CHORD, "4"),
            ("kokonaispituus potkuri mukaan lukien", allbb.max.X - min(allbb.min.X, 0), m.RULE_LENGTH, "5"),
            ("koukkuväli", m.HOOK_TO_HOOK, m.RULE_HOOK_TO_HOOK, "7")]


def rules_md(solids) -> str:
    out = ["| Sääntö | Mitta | Malli mm | Raja mm | |", "|---:|---|---:|---:|---|"]
    for name, val, lim, rule in rule_rows(solids):
        out.append(f"| {rule} | {name} | {fi(val, 1)} | {fi(lim, 1)} | {'✅' if val <= lim else '❌ ylittyy'} |")
    over = [name for name, val, lim, _ in rule_rows(solids) if val > lim]
    if over:
        out += ["", f"> **Huom.** Malli ylittää P-18-rajan: {', '.join(over)}. Kilpailukoneessa nämä "
                "mitat pitää pienentää rajojen sisään."]
    return "\n".join(out)


def tech_md(solids, info) -> str:
    sp = info["spans"]
    w = Compound(solids["wing"]).bounding_box()
    allbb = Compound([x for g in solids.values() for x in g]).bounding_box()
    rows = [
        ("Siipi", f"{fi(sp['L'] + sp['R'], 0)} mm rimoja pitkin (vasen {fi(sp['L'], 0)}, oikea {fi(sp['R'], 0)}), "
                  f"projektio {fi(w.size.Y, 1)} mm, jänne {fi(info['chord'], 0)} mm"),
        ("V-kulma", f"{fi(info['dihedral'], 2)}° kummallakin puoliskolla (DXF-riman 9 tyviviiste)"),
        ("Asetuskulma / wash-in", f"siipi +{fi(m.WING_INCIDENCE, 0)}° kiilalla, vasemman siiven jättöreuna kärjessä "
                                  f"{fi(m.WASH_IN_LEFT, 0)} mm alempana"),
        ("Korkeusvakaaja", f"{fi(Compound(solids['stab']).bounding_box().size.Y, 0)} × {fi(info['stab_chord'], 1)} mm, "
                           f"tasainen, {len(m.STAB_RIBS)} kaarta, kallistus ±{fi(m.STAB_TILT, 0)} mm"),
        ("Sivuperäsin", f"{fi(m.RUDDER_ROOT, 0)}/{fi(m.RUDDER_TIP, 0)} × {fi(m.RUDDER_HEIGHT, 0)} mm, "
                        f"kääntyvä, {fi(m.RUDDER_TURN, 0)}° vasemmalle"),
        ("Runkotikku", f"{fi(m.STICK_H, 0)} × {fi(m.STICK_W, 0)} × {fi(m.STICK_LEN, 0)} mm balsaa, takapää kapenee "
                       f"{fi(m.STICK_H_TAIL, 0)} mm:iin; hiilikuitulatat 0,1 × 1 mm päällä ja alla"),
        ("Koukkuväli", f"{fi(m.HOOK_TO_HOOK, 0)} mm"),
        ("Vetoviiva", f"{drawing.thrust_text()}; akseli {fi(-m.MOUNT_THRUST_Z - m.STICK_H, 1)} mm tikun alapinnan alapuolella"),
        ("Kokonaispituus", f"{fi(allbb.max.X - min(allbb.min.X, 0), 0)} mm"),
        ("Potkuri", "6\" kaupallinen muovipotkuri, laakeri 2 lasihelmeä + ≥ 3 mylar-prikkaa, teflonöljy"),
        ("Materiaalit", "balsa 60–70 kg/m³ (2 mm ja 4 mm levyt), moottoripukki PETG, kalvo mylar 2 µm + 3M77"),
    ]
    return "\n".join(["| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows])


def fill(text: str, key: str, body: str) -> str:
    pat = re.compile(rf"(<!-- BEGIN:{key} -->)\n.*?(<!-- END:{key} -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"README.md: lohko {key} puuttuu")
    return pat.sub(lambda mm: mm.group(1) + "\n" + body + "\n" + mm.group(2), text)


# --------------------------------------------------------------------------
# pictures
# --------------------------------------------------------------------------
AXES = [  # (axis, name, colour)
    ((0, 0, 1), "Z-akselin (pystyakseli) ympäri — suunta, yaw", "#1f6fd1"),
    ((1, 0, 0), "X-akselin (pituusakseli) ympäri — kallistus, roll", "#d1361f"),
    ((0, 1, 0), "Y-akselin (poikittaisakseli) ympäri — nyökkäys, pitch", "#1f9d4c"),
]


def rotating_svg(shapes, path: Path, per_axis=20, seconds_per_axis=8.0, width=880,
                 camera=(-0.66, 0.66, 0.37)):
    """Animated SVG: the model makes a full turn about Z, then X, then Y (about its
    own center), seen from a fixed camera; visible edges only, the axis dashed."""
    from build123d import Axis

    comp = Compound(shapes)
    c = comp.bounding_box().center()
    comp = Compound([s.moved(Location((-c.X, -c.Y, -c.Z))) for s in shapes])
    cam = tuple(v * 3000 for v in camera)
    frames = []  # (axis index, angle, lines, axis line)
    for k, (ax, _, _) in enumerate(AXES):
        for i in range(per_axis):
            ang = 360 * i / per_axis
            rc = comp.rotate(Axis((0, 0, 0), ax), ang)
            vis, _ = rc.project_to_viewport(cam, (0, 0, 1), look_at=(0, 0, 0))
            lines = []
            for e in vis:
                if e.geom_type == GeomType.LINE:
                    ps = [e.position_at(0), e.position_at(1)]
                else:
                    n = max(3, int(e.length / 2.0))
                    ps = [e.position_at(t / n) for t in range(n + 1)]
                lines.append([(p.X, p.Y) for p in ps])
            frames.append((k, ang, lines))
    # the axes in the same 2D frame as the edges
    from build123d import Vector
    nv = Vector(camera).normalized()
    xv = Vector(0, 0, 1).cross(nv).normalized()
    yv = nv.cross(xv)

    def p2(P):
        P = Vector(P)
        return P.dot(xv), P.dot(yv)
    ext_x = max(abs(x) for _, _, v in frames for l in v for x, _ in l)
    ext_y = max(abs(y) for _, _, v in frames for l in v for _, y in l)
    s = (width / 2 - 20) / ext_x
    height = int(2 * ext_y * s + 70)
    cx, cy = width / 2, height / 2 + 8
    n = len(frames)
    cycle = seconds_per_axis * len(AXES)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           "<title>Iltatähti P-18 — 3D, pyörähdykset X-, Y- ja Z-akselien ympäri</title>",
           f"<style>.f{{opacity:0;animation:k {cycle:g}s step-end infinite}}.f0{{opacity:1}}"
           f"@keyframes k{{0%{{opacity:1}}{100 / n:.4f}%{{opacity:0}}100%{{opacity:0}}}}"
           ".m{fill:none;stroke:#1d2733;stroke-width:0.8;stroke-linejoin:round;stroke-linecap:round}"
           ".a{fill:none;stroke-width:1.4;stroke-dasharray:8 4}"
           "text{font-family:sans-serif}</style>",
           f'<rect width="{width}" height="{height}" rx="10" fill="#ffffff"/>']
    for i, (k, ang, lines) in enumerate(frames):
        ax, name, col = AXES[k]
        d = []
        for l in lines:
            pts = list(LineString([(cx + x * s, cy - y * s) for x, y in l]).simplify(0.25).coords)
            d.append(f"M{pts[0][0]:.1f} {pts[0][1]:.1f}" + "".join(f"L{x:.1f} {y:.1f}" for x, y in pts[1:]))
        a0, a1 = p2(tuple(-320 * v for v in ax)), p2(tuple(320 * v for v in ax))
        axis = (f'<path class="a" stroke="{col}" d="M{cx + a0[0] * s:.1f} {cy - a0[1] * s:.1f}'
                f'L{cx + a1[0] * s:.1f} {cy - a1[1] * s:.1f}"/>')
        label = (f'<text x="18" y="30" font-size="16" font-weight="bold" fill="{col}">{name}</text>'
                 f'<text x="18" y="50" font-size="13" fill="#6b7785">{ang:.0f}°</text>')
        cls = "f f0" if i == 0 else "f"
        out.append(f'<g class="{cls}" style="animation-delay:{cycle * i / n:.3f}s">{axis}'
                   f'<path class="m" d="{"".join(d)}"/>{label}</g>')
    out.append(f'<text x="{width - 14}" y="{height - 12}" text-anchor="end" font-size="12" fill="#6b7785">'
               "Iltatähti P-18 · pyörähdykset Z-, X- ja Y-akselin ympäri</text>")
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


def iso_svg(shapes, path: Path, width=1000, margin=20):
    """The building drawing's whole-model 3D view (same direction as drawing.py's
    iso_all): visible edges solid, hidden edges thin grey dashes."""
    v = drawing.View(shapes, (-1, -1.25, 0.75), (0, 0, 1), scale=1e9, hidden=True).fit(width - 2 * margin)
    w, h = v.size
    height = int(h + 2 * margin + 40)
    v.place_tl(margin, margin + 34)

    def d(edges):
        out = []
        for e in edges:
            pts = list(LineString([v.s2(x, y) for x, y in e]).simplify(0.15).coords) if len(e) > 1 else []
            if len(pts) > 1:
                out.append(f"M{pts[0][0]:.1f} {pts[0][1]:.1f}" + "".join(f"L{x:.1f} {y:.1f}" for x, y in pts[1:]))
        return "".join(out)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f"<title>{m.MODEL_NAME} — 3D</title>",
           f'<rect width="{width}" height="{height}" rx="10" fill="#ffffff"/>',
           f'<text x="{margin}" y="{margin + 6}" font-family="sans-serif" font-size="18" font-weight="bold" '
           f'fill="#000">{m.MODEL_NAME.upper()} — 3D</text>',
           f'<text x="{margin}" y="{margin + 24}" font-family="sans-serif" font-size="12" fill="#444">'
           "6\" muovipotkuri (havainnekuva); katkoviiva = piilossa oleva särmä</text>",
           f'<path d="{d(v.hid)}" fill="none" stroke="#777" stroke-width="0.5" stroke-dasharray="4 2.5"/>',
           f'<path d="{d(v.vis)}" fill="none" stroke="#000" stroke-width="1" stroke-linejoin="round" '
           'stroke-linecap="round"/>',
           "</svg>"]
    path.write_text("\n".join(svg) + "\n")


def light_model(simplify=0.25):
    """The model again with every balsa outline simplified (README 3D viewer only):
    far fewer triangles, no visible difference at screen size."""
    import to_laser

    orig = m.FlatPart.solid

    def solid(part, loc=Location()):
        poly = to_laser.profile_raw(part).simplify(simplify)

        def wire(ring):
            return Wire.make_polygon([(x, y, 0) for x, y in list(ring.coords)[:-1]], close=True)
        face = Face(wire(poly.exterior), [wire(r) for r in poly.interiors])
        return orig(dataclasses.replace(part, profile=face), loc)
    m.FlatPart.solid = solid
    try:
        solids, _, _ = m.build()
    finally:
        m.FlatPart.solid = orig
    return [x for g in solids.values() for x in g]


def drawing_png(path: Path, width=3600):
    pdf = HERE / "piirustus" / "ILT-P18-001_A.pdf"
    subprocess.run(["pdftoppm", "-png", "-singlefile", "-scale-to-x", str(width), "-scale-to-y", "-1",
                    str(pdf), str(path.with_suffix(""))], check=True)


def main():
    DOCS.mkdir(exist_ok=True)
    solids, flat, info = m.build()
    allp = [x for g in solids.values() for x in g]
    mount_bb = next(s for s in solids["hardware"] if s.label == "pukki").bounding_box()
    prop, _, _ = drawing.prop_solid(mount_bb)

    iso_svg(allp + [prop], DOCS / "iltatahti_iso.svg")
    light = light_model()
    rotating_svg(light + [prop], DOCS / "iltatahti_3d.svg")
    drawing_png(DOCS / "rakennuspiirustus.png")
    export_stl(Compound(allp), str(m.STEP_DIR / f"{m.MODEL_ID}.stl"), tolerance=0.05, angular_tolerance=0.3)

    rows, groups, extra = budget(solids, flat, info)
    text = README.read_text(encoding="utf-8")
    text = fill(text, "tekniset", tech_md(solids, info))
    text = fill(text, "saannot", rules_md(solids))
    text = fill(text, "paino", budget_md(rows, groups, extra))
    README.write_text(text, encoding="utf-8")
    for f in (DOCS / "iltatahti_3d.svg", DOCS / "iltatahti_iso.svg", DOCS / "rakennuspiirustus.png", m.STEP_DIR / f"{m.MODEL_ID}.stl"):
        print(f"{f.relative_to(HERE)}: {f.stat().st_size / 1024:.0f} kB")
    print("README.md: tekniset tiedot, sääntötarkistus ja painobudjetti päivitetty")


if __name__ == "__main__":
    main()
