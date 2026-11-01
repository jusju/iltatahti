"""Rubber-model airplane propeller shaft bracket, V3 rear-edge rib anchors.

X: from fuselage socket toward propeller shaft (center separation 12 mm)
Y: transverse, negative = left
Z: sleeve axis and FDM build direction (Z=0 bed)

Both ribs anchor to rearward (fuselage-facing) sector of the small shaft bushing
at x=10.7 instead of around its center; the other ends meet the large socket
close to its far Z rim, and their cone cores penetrate inside the socket wall.
The shaft tilts 2 degrees left. The face-plate support is widened in Y and
thickened in Z by 1.5x, otherwise functional dimensions remain V2-compatible.
Only simple parameterized design; not SIMP/automatic topology optimization.
"""
import cadquery as cq
import numpy as np
import math, json, csv
from pathlib import Path
import trimesh
P=Path(__file__).resolve().parent
V=cq.Vector

def conical_strut(a,b,r0,r1):
    p=V(*a); q=V(*b); w=q-p
    return cq.Solid.makeCone(r0,r1,w.Length,p,w.normalized())

OLD_PLATE=[(4.85,-1.35),(6.3,-.78),(10.8,-.60),(12.0,-1.1),
           (12.0,1.1),(10.8,.60),(6.3,.78),(4.85,1.35)]

def build(depth=10,style='V3'):
    if depth not in (5,10):raise ValueError(depth)
    # Keep original 11.7 mm socket outside, 10.2 mm bore, 1.7 mm bearing radius
    socket=cq.Solid.makeCylinder(5.85,depth,V(0,0,0),V(0,0,1))
    bearing=cq.Solid.makeCylinder(1.70,5,V(12,0,0),V(0,0,1))
    solids=[socket,bearing]
    # V2 face strip had thickness 0.72 mm. Increase lateral breadth and Z thickness by 1.5.
    face_poly=[(x,y*1.5) for x,y in OLD_PLATE]
    face=cq.Workplane('XY').polyline(face_poly).close().extrude(.72*1.5).val()
    solids.append(face)
    if style=='V3':
        for sign in (-1,1):
            # Small bearing rearward edge: center x=12, radius 1.70,
            # rib tip x=10.70 is 1.30 mm from center in X.
            a=(10.70,sign*.38,1.10)
            # Large socket: root center at r~5.24 mm inside 5.10..5.85 wall;
            # cone cuts deeply into socket wall (but hole is re-bored afterwards).
            # Root is close to far end in Z (the 'takareuna' of long sleeve).
            b=(4.40,sign*2.85,depth-.45)
            solids.append(conical_strut(a,b,.76,.94))
            # Rib-to-small-bushing root blend
            solids.append(cq.Solid.makeSphere(.83,V(*a)))
    elif style=='plate':
        # Comparison case, with exactly same wider foot/face strip as V3.
        solids.append(conical_strut((10.95,0,1.0),(4.97,0,depth*.76),.95,.96))
    else:raise ValueError(style)
    part=solids[0]
    for s in solids[1:]:part=part.fuse(s)
    # Re-machine the large bore and shaft hole at the end for through-holes.
    part=part.cut(cq.Solid.makeCylinder(5.1,depth+2,V(0,0,-1),V(0,0,1)))
    tilt=math.radians(2)
    axis=V(0,-math.sin(tilt),math.cos(tilt))
    part=part.cut(cq.Solid.makeCylinder(.475,8,V(12,0,2.5)-axis*4,axis))
    # Do not let round rib end exceed sleeve top; no protruding Z-positive crown.
    part=part.intersect(cq.Solid.makeBox(40,40,depth,V(-10,-20,0)))
    return part.clean()

if __name__=='__main__':
    data=[]
    for depth in (5,10):
        for variant in ('plate','V3'):
            obj=build(depth,variant)
            name=f'pukki_{variant}_{depth}mm_Z'
            stl=P/f'{name}.stl'; step=P/f'{name}.step'
            cq.exporters.export(obj,str(stl),tolerance=.025,angularTolerance=.11)
            cq.exporters.export(obj,str(step))
            m=trimesh.load_mesh(stl)
            row=dict(name=name,depth_mm=depth,design=variant,volume_mm3=round(obj.Volume(),3),
                     PLA_g=round(obj.Volume()*.00124,5),PETG_g=round(obj.Volume()*.00127,5),
                     watertight=bool(m.is_watertight),components=len(m.split(only_watertight=False)),
                     z_min_mm=round(float(m.bounds[0,2]),5),bounds_mm=np.round(m.extents,3).tolist())
            data.append(row);print(row,flush=True)
    (P/'massa_ja_geometriatarkistus.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    with (P/'painoarviot.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['name','depth_mm','design','volume_mm3','PLA_g','PETG_g','watertight','components','z_min_mm']);w.writeheader();w.writerows({k:v for k,v in item.items() if k in w.fieldnames} for item in data)
