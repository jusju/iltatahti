"""
6propeller.py — a 6 inch (152.4 mm) two blade propeller for the Iltatähti P-18, to be
printed in PLA. Run it as a script: .venv/bin/python 6propeller.py [--no-viewer]

Designed for the model's cruise: blades shaped for minimum induced loss at the design
point (Betz / Larrabee optimum, Adkins & Liebeck 1994): chord and blade angle at every
radius come from the flight speed, the rpm and the thrust the model needs.

  design point   model 7.5 g with the prop + rubber (40" loop, 2.5 x 1.07 mm Tan II)
                 = flying weight; level flight at CL_CRUISE on the wing area; thrust =
                 weight / L/D; rpm from the launch turns and the motor run time
  blades         thin cambered plate sections (CAMBER), thickness from ROOT_T to TIP_T,
                 sections wrapped on their radius; rounded tip; right-hand prop (turns
                 clockwise seen from behind, pulling forward)
  hub            6 mm, 7 mm long, 0.8 mm shaft hole; on the front face a groove across
                 the hub: the bent end of the shaft lies in it and drives the prop

Note: P-18 contest rule 6 asks for an unmodified commercial plastic prop: a printed prop
is for practice and sport flying.

Writes step/6propeller.step and step/6propeller.stl (prop axis = Z, front = +Z).
"""

import argparse
from math import atan, cos, pi, radians, sin, sqrt
from pathlib import Path

import numpy as np
from build123d import Align, Box, Compound, Cylinder, Location, Solid, Wire, export_step, export_stl

HERE = Path(__file__).parent
OUT = HERE / "step"

# ---- model and rubber -------------------------------------------------------
MODEL_G = 7.5  # model with the prop, without rubber
RUBBER_L, RUBBER_W, RUBBER_T, RUBBER_RHO = 1016.0, 2.5, 1.07, 0.96  # mm, mm, mm, g/cm3 (40" strip, Tan II)
WING_AREA = 0.0384  # m2 (245 + 235 mm x 80 mm)
CL_CRUISE = 0.9  # wing lift coefficient in the slow indoor cruise
L_OVER_D = 6.0  # whole model
LAUNCH_TURNS, MOTOR_RUN_S = 1250, 100.0  # turns at launch (README: 2.5 mm loop) and motor run
RHO = 1.20  # air kg/m3

# ---- propeller --------------------------------------------------------------
D = 152.4e-3  # 6 inch
B = 2
HUB_R, HUB_L = 3.0, 7.0  # mm
HOLE_D = 0.8  # shaft hole
GROOVE_W, GROOVE_DEPTH = 0.9, 0.9  # shaft lock groove on the front face
CL_BLADE, CD_BLADE, ALPHA_DEG = 0.8, 0.055, 5.0  # thin cambered plate at Re ~ 10 000
CAMBER = 0.05  # camber / chord
ROOT_T, TIP_T, TE_T = 1.2, 0.6, 0.35  # mm: max thickness at the root and the tip, trailing edge
TIP_CHORD = 5.0  # mm: rounded tip, the optimum chord goes to zero there
MAX_CHORD = 28.0  # mm
PLA = 1.24  # g/cm3
STATIONS = 22


def design_point():
    rubber_g = RUBBER_L * RUBBER_W * RUBBER_T / 1000 * RUBBER_RHO
    w = (MODEL_G + rubber_g) / 1000 * 9.81
    v = sqrt(2 * w / (RHO * WING_AREA * CL_CRUISE))
    thrust = w / L_OVER_D
    n = LAUNCH_TURNS / MOTOR_RUN_S  # rev/s
    return dict(rubber_g=rubber_g, weight_n=w, v=v, thrust=thrust, n=n)


def larrabee(v, n, thrust, r_hub):
    """Adkins & Liebeck design for a given thrust: radius (m), chord (m), blade angle
    (rad), efficiency, power (W), torque (N m)."""
    R = D / 2
    om = 2 * pi * n
    lam = v / (om * R)
    eps = CD_BLADE / CL_BLADE
    xi = np.linspace(r_hub / R, 1.0, 200)
    tc = 2 * thrust / (RHO * v ** 2 * pi * R ** 2)
    zeta = 0.0
    for _ in range(100):
        phit = atan(lam * (1 + zeta / 2))
        f = B / 2 * (1 - xi) / sin(phit)
        F = 2 / pi * np.arccos(np.exp(-f))
        phi = np.arctan(np.tan(phit) / xi)
        x = om * xi * R / v
        G = F * x * np.cos(phi) * np.sin(phi)
        a = zeta / 2 * np.cos(phi) ** 2 * (1 - eps * np.tan(phi))
        W = v * (1 + a) / np.sin(phi)
        chord = 4 * pi * lam * G * v * R * zeta / (CL_BLADE * B) / W
        i1 = np.trapezoid(4 * xi * G * (1 - eps * np.tan(phi)), xi)
        i2 = np.trapezoid(lam * (4 * G * (1 - eps * np.tan(phi)) / 2) * (1 + eps / np.tan(phi))
                          * np.sin(phi) * np.cos(phi), xi)
        j1 = np.trapezoid(4 * xi * G * (1 + eps / np.tan(phi)), xi)
        j2 = np.trapezoid(2 * xi * G * (1 + eps / np.tan(phi)) * (1 - eps * np.tan(phi)) * np.cos(phi) ** 2, xi)
        new = i1 / (2 * i2) * (1 - sqrt(max(0.0, 1 - 4 * i2 * tc / i1 ** 2)))
        if abs(new - zeta) < 1e-9:
            break
        zeta = new
    pc = j1 * zeta + j2 * zeta ** 2
    power = pc * RHO * v ** 3 * pi * R ** 2 / 2
    return xi * R, chord, phi + radians(ALPHA_DEG), tc / pc, power, power / om


def section(chord, t_max):
    """Thin cambered plate section: closed outline (s along the chord 0..1 from the LE,
    y up = suction side), in mm."""
    k = np.linspace(0, pi, 24)
    s = (1 - np.cos(k)) / 2
    yc = 4 * CAMBER * chord * s * (1 - s)
    naca = 5 * (0.2969 * np.sqrt(s) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1036 * s ** 4) / 0.1
    t = TE_T + (t_max - TE_T) * naca / naca.max()
    upper = [(si * chord, y + ti / 2) for si, y, ti in zip(s, yc, t)]
    lower = [(si * chord, y - ti / 2) for si, y, ti in zip(s, yc, t)]
    return upper[::-1] + lower[1:-1]  # TE -> LE on top, LE -> TE below (closed)


def blade_wire(r, chord, beta, t_max):
    """Section at radius r (mm), wrapped on the cylinder r. Right-hand prop: the blade at
    +X moves to +Y; the LE is ahead (+Y) and forward (+Z) of the TE."""
    pts = []
    for s, y in section(chord, t_max):
        u = s - 0.40 * chord  # blade stacked at 40 % chord
        # chord from LE to TE: -(cos b) Y - (sin b) Z; suction side normal: -(sin b) Y + (cos b) Z
        tang = -u * cos(beta) - y * sin(beta)
        ax = -u * sin(beta) + y * cos(beta)
        th = tang / r
        pts.append((r * cos(th), r * sin(th), ax))
    return Wire.make_polygon(pts, close=True)


def build():
    dp = design_point()
    r, c, beta, eta, power, torque = larrabee(dp["v"], dp["n"], dp["thrust"], HUB_R / 1000)
    R = D / 2 * 1000
    rs = HUB_R - 1.0 + (R - 0.3 - (HUB_R - 1.0)) * (1 - np.cos(np.linspace(0, pi / 2, STATIONS)))  # tip clustered
    wires, table = [], []
    for ri in rs:
        ci = float(np.interp(ri, r * 1000, c * 1000))
        bi = float(np.interp(ri, r * 1000, beta))
        xi = (ri - HUB_R) / (R - HUB_R)
        tip = TIP_CHORD + (MAX_CHORD - TIP_CHORD) * sqrt(max(0.0, 1 - max(0.0, (ri - 0.8 * R) / (0.2 * R)) ** 2))
        ci = min(max(ci, TIP_CHORD), tip, MAX_CHORD)
        if ri < HUB_R + 4:  # blend into the hub: narrower and thicker root
            ci = min(ci, 6.0 + (ri - HUB_R) * 1.5)
        ti = ROOT_T + (TIP_T - ROOT_T) * min(1.0, max(0.0, xi))
        wires.append(blade_wire(ri, ci, bi, ti))
        table.append((ri, ci, bi, 2 * pi * ri * np.tan(bi)))
    blade = Solid.make_loft(wires)
    blades = [blade, blade.rotate(_z_axis(), 180)]
    hub = Cylinder(HUB_R, HUB_L)
    prop = hub
    for b_ in blades:
        prop = prop + b_
    prop = prop - Cylinder(HOLE_D / 2, HUB_L + 2)
    groove = Location((0, 0, HUB_L / 2)) * Box(GROOVE_W, 2 * HUB_R + 2, 2 * GROOVE_DEPTH)  # across, at the front
    prop = prop - groove
    solids = prop.solids() if hasattr(prop, "solids") else [prop]
    out = max(solids, key=lambda s: s.volume)
    return out, dict(dp=dp, eta=eta, power=power, torque=torque, table=table)


def _z_axis():
    from build123d import Axis
    return Axis.Z


def main(viewer=True):
    prop, info = build()
    dp = info["dp"]
    mass = prop.volume / 1000 * PLA
    p75 = np.interp(0.75 * D / 2 * 1000, [t[0] for t in info["table"]], [t[3] for t in info["table"]])
    print(f"Toimintapiste: lentopaino {MODEL_G + dp['rubber_g']:.1f} g (kumi {dp['rubber_g']:.2f} g), "
          f"nopeus {dp['v']:.2f} m/s, veto {dp['thrust'] * 1000:.1f} mN, {dp['n'] * 60:.0f} rpm")
    print(f"Potkuri: hyötysuhde {info['eta'] * 100:.0f} %, teho {info['power'] * 1000:.0f} mW, vääntö "
          f"{info['torque'] * 1000:.2f} mN·m; nousu 0,75 R:llä {p75:.0f} mm (P/D {p75 / (D * 1000):.2f})")
    print("  r mm   jänne mm   kulma °   nousu mm")
    for ri, ci, bi, pi_ in info["table"][::3] + [info["table"][-1]]:
        print(f"  {ri:5.1f}  {ci:7.1f}  {np.degrees(bi):7.1f}  {pi_:8.0f}")
    bb = prop.bounding_box()
    print(f"Halkaisija {bb.size.X:.1f} mm, napa ⌀{2 * HUB_R:g} × {HUB_L:g} mm, reikä ⌀{HOLE_D:g} mm, "
          f"lukitusura {GROOVE_W:g} × {GROOVE_DEPTH:g} mm etupinnassa; tilavuus {prop.volume:.0f} mm³ = "
          f"{mass:.2f} g PLA:na (100 % täyttö)")
    OUT.mkdir(exist_ok=True)
    src = Path(__file__).stem
    prop.label = f"{Path(__file__).name}: potkuri 6\""
    export_step(prop, OUT / f"{src}.step")
    export_stl(prop, str(OUT / f"{src}.stl"), tolerance=0.02, angular_tolerance=0.1)
    print(f"3D: step/{src}.step, step/{src}.stl")
    if viewer:
        try:
            from ocp_vscode import Camera, show

            show(prop, names=[prop.label], reset_camera=Camera.RESET)
        except Exception as e:  # viewer not running
            print(f"OCP viewer ei ole käytettävissä: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="6\" potkuri Iltatähti P-18:aan, PLA-tulostukseen")
    ap.add_argument("--no-viewer", action="store_true", help="älä lähetä mallia OCP CAD Vieweriin")
    main(viewer=not ap.parse_args().no_viewer)
