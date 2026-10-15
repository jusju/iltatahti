"""
pukki.py — the 3D printed motor mount ("pukki") of the Iltatähti P-18, parametric.

Rebuilt from pukki-v6.step (the measured original, kept as the reference): with
sivuveto = 2, alaveto = 0, tikun_korkeus = 9 and taskun_vara = 1 this gives the
same part. The values come from pukki.txt.

Mount coordinates (as in pukki-v6.step):
  X across the stick (+X = right wing), Y up, Z aft along the stick.
  Body 6 wide, 11 long: the stick pocket 4 x (stick height + taskun_vara), 10 deep,
  opens aft (+Z), its top level with the stick top (Y = 6); a 1 mm slot under it,
  three 1 mm pin holes across. Below the body a 1.2 mm web, widened into the body
  with R2 fillets, carries the prop shaft bearing tube (outer 2 mm, 7.5 long, axis
  along Z). Everything below the pocket moves with the pocket bottom, so the shaft
  stays 9.8 mm below the stick bottom whatever the stick height.
  The web and the tube turn about the bearing's front end (the prop end), so the
  prop stays where it is: sivuveto about Y, alaveto about X.

Run:  .venv/bin/python pukki.py           writes step/pukki.step and step/pukki.stl
      .venv/bin/python pukki.py --check   compares sivuveto 2 / alaveto 0 with pukki-v6.step
"""

import argparse
import re
from pathlib import Path

from build123d import (
    Align,
    Box,
    Circle,
    Cylinder,
    Location,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    Solid,
    export_step,
    export_stl,
    extrude,
    import_step,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pukki.txt"
REFERENCE = HERE / "pukki-v6.step"
OUT_DIR = HERE / "step"
DEFAULTS = {"sivuveto": 3.0, "alaveto": 0.0, "laakerireika": 1.0, "tikun_korkeus": 7.0, "taskun_vara": 1.0}
V6 = {"sivuveto": 2.0, "alaveto": 0.0, "laakerireika": 1.0, "tikun_korkeus": 9.0, "taskun_vara": 1.0}

# dimensions (mm, mount coordinates), measured from pukki-v6.step (pocket 10 high)
BODY_W, BODY_Y1, BODY_L = 6.0, 7.0, 11.0
POCKET_W, POCKET_Y1, POCKET_Z0 = 4.0, 6.0, 1.0  # pocket top = stick top
V6_POCKET_H = 10.0  # the Y values below are for this pocket height ...
V6_POCKET_Y0, V6_SLOT_Y0, V6_SLOT_Y1, V6_BODY_Y0 = -4.0, -6.0, -5.0, -7.0
V6_FILLET_Y, V6_BEARING_Y = -9.0, -12.8  # ... and move up as the pocket gets lower
PIN_R = 0.5
PINS = [(-1.2007, 5.5), (3.0, 7.0), (3.0, 3.1429)]  # (Y, Z) for the 9 mm stick, holes along X;
# their heights scale with the stick height (measured down from the stick top)
WEB_T = 1.2
FILLET_R = 2.0
BEARING_Z0, BEARING_L = -4.0, 7.5  # front end (pivot) and length
BEARING_R = 1.0

POCKET_TOP = POCKET_Y1  # used by p18_iltatahti.py
POCKET_BOTTOM = POCKET_Z0


def dims(cfg: dict) -> dict:
    """The Y values that depend on the pocket height (stick height + clearance)."""
    up = V6_POCKET_H - (cfg["tikun_korkeus"] + cfg["taskun_vara"])
    d = {"pocket_y0": V6_POCKET_Y0 + up, "slot_y0": V6_SLOT_Y0 + up, "slot_y1": V6_SLOT_Y1 + up,
         "body_y0": V6_BODY_Y0 + up, "fillet_y": V6_FILLET_Y + up, "bearing_y": V6_BEARING_Y + up}
    h = cfg["tikun_korkeus"]
    d["pins"] = [(POCKET_Y1 - (POCKET_Y1 - y) * h / V6["tikun_korkeus"], z) for y, z in PINS]
    for y, _ in d["pins"]:
        if not POCKET_Y1 - h + PIN_R + 0.3 <= y <= POCKET_Y1 - PIN_R - 0.3:
            raise ValueError(f"pukki: tappireikä Y {y:g} ei osu {h:g} mm tikkuun")
    by, b0, bt = d["bearing_y"], d["body_y0"], BEARING_Z0 + BEARING_L
    # web outline in the Y-Z plane (before turning): underside from the bearing front up
    # to the body front edge, top from the bearing rear end to the body bottom rear edge
    d["web_yz"] = [(by, BEARING_Z0), (by + 0.8, BEARING_Z0), (BODY_Y1, 0.0), (BODY_Y1, 0.5),
                   (b0 + 0.5, 0.5), (b0 + 0.5, BODY_L), (b0, BODY_L), (by + 0.85, bt), (by, bt)]
    d["pivot"] = (0.0, by, BEARING_Z0)
    return d


def read_config(path: Path = CONFIG) -> dict:
    """key = value lines, # comments; decimal comma accepted."""
    cfg = dict(DEFAULTS)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.fullmatch(r"([A-Za-z_äöÄÖ]+)\s*=\s*([-+]?[\d.,]+)", line)
            if not m or m.group(1) not in DEFAULTS:
                raise ValueError(f"{path.name}: tuntematon rivi '{line}' (sallitut: {', '.join(DEFAULTS)})")
            cfg[m.group(1)] = float(m.group(2).replace(",", "."))
    if not (-10 <= cfg["sivuveto"] <= 10 and -10 <= cfg["alaveto"] <= 10):
        raise ValueError(f"{path.name}: kulmat -10 ... 10 astetta")
    if not 0.5 <= cfg["laakerireika"] <= 1.6:
        raise ValueError(f"{path.name}: laakerireika 0,5 ... 1,6 mm")
    if not (5 <= cfg["tikun_korkeus"] <= 12 and 0 <= cfg["taskun_vara"] <= 2):
        raise ValueError(f"{path.name}: tikun_korkeus 5 ... 12 mm, taskun_vara 0 ... 2 mm")
    return cfg


def turn(sivuveto: float, alaveto: float, pivot) -> Location:
    """Turn about the bearing front end. Left thrust: the front end points to -X
    (left), so the rear end goes to +X; down thrust: the rear end goes up."""
    return Pos(*pivot) * Rot(0, sivuveto, 0) * Rot(-alaveto, 0, 0) * Pos(*(-c for c in pivot))


def build_mount(cfg: dict | None = None) -> Solid:
    cfg = cfg or read_config()
    d = dims(cfg)
    BODY_Y0, POCKET_Y0, SLOT_Y0, SLOT_Y1 = d["body_y0"], d["pocket_y0"], d["slot_y0"], d["slot_y1"]
    FILLET_Y, BEARING_Y = d["fillet_y"], d["bearing_y"]
    body = Pos(0, (BODY_Y0 + BODY_Y1) / 2, 0) * Box(BODY_W, BODY_Y1 - BODY_Y0, BODY_L,
                                                    align=(Align.CENTER, Align.CENTER, Align.MIN))

    # arm: web plate + fillets + bearing tube, all inside the web outline
    outline = extrude(Plane.YZ * Polygon(*d["web_yz"], align=None), amount=BODY_W, both=True)
    plate = Box(WEB_T, 60, 60) & outline
    fl = Plane.XY.offset(-10) * (
        Pos(0, (FILLET_Y + BODY_Y0 + 0.5) / 2) * Rectangle(2 * (WEB_T / 2 + FILLET_R), BODY_Y0 + 0.5 - FILLET_Y)
        - Pos(WEB_T / 2 + FILLET_R, FILLET_Y) * Circle(FILLET_R)
        - Pos(-WEB_T / 2 - FILLET_R, FILLET_Y) * Circle(FILLET_R))
    fillets = extrude(fl, amount=30) & outline
    tube = Pos(0, BEARING_Y, BEARING_Z0) * Cylinder(BEARING_R, BEARING_L, align=(Align.CENTER, Align.CENTER, Align.MIN))
    t = turn(cfg["sivuveto"], cfg["alaveto"], d["pivot"])
    # the fillets meet the body's bottom: only behind its front face (Z >= 0)
    fillets = (t * fillets) & Box(60, 60, 60, align=(Align.CENTER, Align.CENTER, Align.MIN))
    arm = t * (plate + tube) + fillets
    # nothing past the body's sides, top or rear face
    arm = arm & Pos(0, BODY_Y1, BODY_L) * Box(BODY_W, 60, 60, align=(Align.CENTER, Align.MAX, Align.MAX))

    m = body + arm
    m -= Pos(0, (POCKET_Y0 + POCKET_Y1) / 2, POCKET_Z0) * Box(POCKET_W, POCKET_Y1 - POCKET_Y0, BODY_L,
                                                             align=(Align.CENTER, Align.CENTER, Align.MIN))
    m -= Pos(0, (SLOT_Y0 + SLOT_Y1) / 2, POCKET_Z0) * Box(POCKET_W, SLOT_Y1 - SLOT_Y0, BODY_L,
                                                         align=(Align.CENTER, Align.CENTER, Align.MIN))
    for y, z in d["pins"]:
        m -= Pos(0, y, z) * Rot(0, 90, 0) * Cylinder(PIN_R, BODY_W + 2)
    m -= t * (Pos(0, BEARING_Y, BEARING_Z0 - 1) * Cylinder(cfg["laakerireika"] / 2, BEARING_L + 2,
                                                         align=(Align.CENTER, Align.CENTER, Align.MIN)))
    solids = m.solids()
    if len(solids) != 1:
        raise ValueError(f"pukki: {len(solids)} kappaletta, odotettiin 1 (kulmat liian suuret?)")
    out = solids[0]
    out.label = "pukki"
    return out


def write_outputs(cfg: dict | None = None) -> list[Path]:
    cfg = cfg or read_config()
    m = build_mount(cfg)
    OUT_DIR.mkdir(exist_ok=True)
    step, stl = OUT_DIR / "pukki.step", OUT_DIR / "pukki.stl"
    export_step(m, step)
    export_stl(m, stl, tolerance=0.01, angular_tolerance=0.1)
    return [step, stl]


def check(n=60000):
    """Compare with pukki-v6.step: volumes, and random points inside one but not the other."""
    import random

    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    ref = import_step(REFERENCE)
    new = build_mount(V6)
    cr, cn = BRepClass3d_SolidClassifier(ref.wrapped), BRepClass3d_SolidClassifier(new.wrapped)

    def inside(c, p):
        c.Perform(gp_Pnt(*p), 1e-6)
        return c.State() == TopAbs_IN
    b = ref.bounding_box()
    lo, hi = (b.min.X - 0.2, b.min.Y - 0.2, b.min.Z - 0.2), (b.max.X + 0.2, b.max.Y + 0.2, b.max.Z + 0.2)
    vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    rnd = random.Random(1)
    diff = sum(inside(cr, p) != inside(cn, p)
               for p in ((rnd.uniform(lo[0], hi[0]), rnd.uniform(lo[1], hi[1]), rnd.uniform(lo[2], hi[2]))
                         for _ in range(n)))
    print(f"pukki-v6.step {ref.volume:.2f} mm³, parametrinen (2°, 0°, tikku 9) {new.volume:.2f} mm³; "
          f"eroalue ~{diff / n * vol:.1f} mm³ ({diff}/{n} pistettä; pinnan läheltä ~2 mm³ on näytteen kohinaa)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Iltatähti P-18 moottoripukki pukki.txt:n arvoilla")
    ap.add_argument("--check", action="store_true", help="vertaa pukki-v6.step:iin (2°, 0°, tikku 9 mm)")
    args = ap.parse_args()
    if args.check:
        check()
    else:
        cfg = read_config()
        files = write_outputs(cfg)
        print(f"pukki: sivuveto {cfg['sivuveto']:g}° vasemmalle, alaveto {cfg['alaveto']:g}°, "
              f"tasku 4×{cfg['tikun_korkeus'] + cfg['taskun_vara']:g}, laakerireikä ⌀{cfg['laakerireika']:g} "
              f"-> {', '.join(f.relative_to(HERE).as_posix() for f in files)}")
