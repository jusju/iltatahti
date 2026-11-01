"""Two inclined V-ribs carry axial rubber tension as well as lateral and torsional loads.

Coordinates: X = from fuselage tube toward propeller shaft, Y = lateral
(left = negative Y), Z = tube axis, upward while printing. Rubber pulls +Z,
shaft hole inclines -Y at 2 degrees. Front shaft bushing and tube socket touch Z=0.
This is parametric geometry, NOT an optimization solver.
"""
import cadquery as cq
import numpy as np
import math, json
from pathlib import Path
import trimesh
P = Path(__file__).resolve().parent
V=cq.Vector

def conical_strut(a,b,r0,r1):
    p=V(*a); q=V(*b); w=q-p
    return cq.Solid.makeCone(r0,r1,w.Length,p,w.normalized())

def build(depth=10, style='V2'):
    # Both sleeves grow from bed; negative Y is left side-view.
    tube_od=11.7; tube_bore=10.2
    socket=cq.Solid.makeCylinder(tube_od/2,depth,V(0,0,0),V(0,0,1))
    bearing=cq.Solid.makeCylinder(1.70,5,V(12,0,0),V(0,0,1))
    solids=[socket,bearing]
    # Bed-attached slender bridge (front/face-plate replacement): 0.7mm high.
    # Widened tips increase bed attachment and provide a load path at Z~0.
    # This minimal strip is not an extra diagonal support.
    poly=[(4.85,-1.35),(6.3,-.78),(10.8,-.60),(12.0,-1.1),
          (12.0,1.1),(10.8,.60),(6.3,.78),(4.85,1.35)]
    face=cq.Workplane('XY').polyline(poly).close().extrude(.72).val()
    solids.append(face)
    if style=='V2':
        # Main diagonal ribs: broad side V + raised roots on socket; carries Fz!
        # The joint at the shaft is at Z≈1.05, socket anchor Z≈0.9*depth.
        for sign in (-1,1):
            a=(11.55,sign*.25,1.10)
            b=(4.68,sign*3.12,.90*depth)
            solids.append(conical_strut(a,b,.76, .94))
            # Small local cap fillet; makes the rib enter the bearing smoothly.
            solids.append(cq.Solid.makeSphere(.83,V(*a)))
    elif style=='plate':
        # Unbraced plate for comparison; not the recommended design.
        # A slim central plate for reference (axial force path).
        poly2=[(5.10,0,.72),(11.4,0,.72),(11.4,0,3.7),(5.1,0,depth-.35)]
        # tapered cylindrical strut and body bridging (slices)
        solids.append(conical_strut((11.45,0,1.0),(4.97,0,depth*.76),.95,.96))
    else:raise ValueError(style)
    sh=solids[0]
    for s in solids[1:]: sh=sh.fuse(s)
    # Fixed socket/shaft bores; clean through Z=0 to avoid internal support.
    sh=sh.cut(cq.Solid.makeCylinder(5.1,depth+2,V(0,0,-1),V(0,0,1)))
    tilt=math.radians(2.)
    axis=V(0,-math.sin(tilt),math.cos(tilt))
    sh=sh.cut(cq.Solid.makeCylinder(.475,8,V(12,0,2.5)-axis*4,axis))
    return sh.clean()

if __name__=='__main__':
    data=[]
    for depth in (5,10):
        for variant in ('plate','V2'):
            obj=build(depth,variant)
            name=f'pukki_{variant}_{depth}mm_Z'
            sp=P/f'{name}.stl'; st=P/f'{name}.step'
            cq.exporters.export(obj,str(sp),tolerance=.025,angularTolerance=.11)
            cq.exporters.export(obj,str(st))
            mesh=trimesh.load_mesh(sp)
            row=dict(name=name,depth_mm=depth,design=variant,volume_mm3=round(obj.Volume(),3),
                     PLA_g=round(obj.Volume()*.00124,4),PETG_g=round(obj.Volume()*.00127,4),
                     watertight=bool(mesh.is_watertight), parts=len(mesh.split(only_watertight=False)),
                     z_min=round(float(mesh.bounds[0,2]),4),bounding_mm=np.round(mesh.extents,2).tolist())
            data.append(row)
            print(row,flush=True)
    (P/'massa_ja_geometriatarkistus.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
