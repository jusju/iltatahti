"""Coarse 3D SOLID FEM using 8-node isoparametric hex elements on a voxel approximation.

This *is* volumetric 3D FEM with 3 displacement DOFs/node (not a beam surrogate).
It is not a validated stress/strength certification and is particularly sensitive to
voxel edge approximations of the thin (~1.5 mm) ribs.

Requires numpy, scipy, trimesh. Units: mm, N, N/mm2, N*mm.
Load cases: Fz +0.5 N (rubber pull), Fy -0.5*tan(2deg) N (left), Mz 1 Nmm.
Fully clamped inner-sleeve interface = ideal rigid carbon tube (conservative stiffness).
"""
import sys,json,time,math
from pathlib import Path
import numpy as np
import trimesh
from scipy import sparse
from scipy.sparse.linalg import splu

ROOT=Path(__file__).resolve().parent.parent
M=ROOT/'mallit';OUT=ROOT/'laskenta'
E=2000.0; nu=.35
D=E/((1+nu)*(1-2*nu))*np.array([
 [1-nu,nu,nu,0,0,0],[nu,1-nu,nu,0,0,0],[nu,nu,1-nu,0,0,0],
 [0,0,0,(1-2*nu)/2,0,0],[0,0,0,0,(1-2*nu)/2,0],[0,0,0,0,0,(1-2*nu)/2]],float)
CORNERS=np.array([(0,0,0),(1,0,0),(1,1,0),(0,1,0),
                  (0,0,1),(1,0,1),(1,1,1),(0,1,1)],dtype=int)
SIGNS=CORNERS*2-1

def strain_matrix(dx,xi,eta,zeta):
    v=np.array([xi,eta,zeta]);der=np.empty((8,3))
    for a,sg in enumerate(SIGNS):
        for k in range(3):
            other=[j for j in range(3) if j!=k]
            der[a,k]=sg[k]/8*np.prod(1+sg[other]*v[other])/(dx/2)
    B=np.zeros((6,24),float)
    for a,(gx,gy,gz) in enumerate(der):
        j=3*a
        B[0,j]=gx;B[1,j+1]=gy;B[2,j+2]=gz
        B[3,j]=gy;B[3,j+1]=gx
        B[4,j+1]=gz;B[4,j+2]=gy
        B[5,j]=gz;B[5,j+2]=gx
    return B

def element_matrix(dx):
    Ke=np.zeros((24,24))
    for xi in (-1/np.sqrt(3),1/np.sqrt(3)):
      for eta in (-1/np.sqrt(3),1/np.sqrt(3)):
       for zeta in (-1/np.sqrt(3),1/np.sqrt(3)):
        B=strain_matrix(dx,xi,eta,zeta)
        Ke += B.T@D@B * (dx/2)**3
    return Ke

def assemble(mesh,pitch):
    vox=mesh.voxelized(pitch).fill()
    mask=vox.matrix
    indices=np.argwhere(mask)
    # Place brick corners at voxel center +- pitch/2.
    offsets=np.asarray(vox.transform)[:3,3]
    corners=indices[:,None,:]+CORNERS[None,:,:]
    compact, inverse=np.unique(corners.reshape((-1,3)),axis=0,return_inverse=True)
    xyz=offsets+pitch*(compact-.5)
    enodes=inverse.reshape((-1,8))
    edofs=(enodes[:,:,None]*3+np.arange(3)[None,None,:]).reshape((-1,24))
    Ke=element_matrix(pitch)
    # Sparse matrix coo assembly; many repeated edges combined in CSR
    er=np.broadcast_to(edofs[:,:,None],(len(edofs),24,24)).ravel()
    ec=np.broadcast_to(edofs[:,None,:],(len(edofs),24,24)).ravel()
    ev=np.tile(Ke.ravel(),len(edofs))
    K=sparse.coo_matrix((ev,(er,ec)),shape=(len(compact)*3,len(compact)*3)).tocsr()
    return vox, xyz, enodes, edofs, K, Ke

def find_supports(xyz,depth):
    x,y,z=xyz.T;r=np.hypot(x,y)
    # inner cylindrical sleeve bonded to fixed fuselage tube, idealized clamping
    candidates=np.flatnonzero((r>=4.65)&(r<=5.55)&(z>=.1)&(z<=depth-.1))
    # If pitch grid samples don't align precisely with wall, broaden slightly
    if len(candidates)<20:
        candidates=np.flatnonzero((r>=4.3)&(r<=5.8)&(z>=.1)&(z<=depth-.1))
    return candidates

def load_and_solve(path,pitch=.7):
    t0=time.time()
    mesh=trimesh.load_mesh(path)
    vox,xyz,enodes,edofs,K,Ke=assemble(mesh,pitch)
    depth=5 if '5mm' in path.name else 10
    fixed_nodes=find_supports(xyz,depth)
    x,y,z=xyz.T
    # Load into the 3D shaft bushing material excluding central bore.
    hub=np.flatnonzero((x>10.9)&(x<13.15)&(abs(y)<1.65)&(z>1.05)&(z<3.95))
    assert len(hub)>3,(len(hub),pitch)
    all_dofs=np.arange(len(xyz)*3)
    fixed=np.repeat(fixed_nodes*3,3)+np.tile(np.arange(3),len(fixed_nodes))
    free=np.setdiff1d(all_dofs,fixed,assume_unique=False)
    sub=K[free,:][:,free].tocsc()
    solver=splu(sub,permc_spec='COLAMD')
    F0=.5
    cases={}
    vectors={
      'rubber_Fz_0p5N':np.zeros(len(xyz)*3),
      'left_Fy_2deg':np.zeros(len(xyz)*3),
      'shaft_torsion_Mz_1Nmm':np.zeros(len(xyz)*3),
    }
    vectors['rubber_Fz_0p5N'][hub*3+2]=F0/len(hub)
    vectors['left_Fy_2deg'][hub*3+1]=-F0*math.tan(math.radians(2))/len(hub)
    # Pure z-axis couple on the cylindrical bearing around its centroid; no net force
    hx=xyz[hub,0]; hy=xyz[hub,1]; dx=hx-hx.mean();dy=hy-hy.mean()
    den=(dx**2+dy**2).sum()
    vectors['shaft_torsion_Mz_1Nmm'][hub*3]   =-dy/den
    vectors['shaft_torsion_Mz_1Nmm'][hub*3+1] = dx/den
    combined=sum(vectors.values())
    vectors['combined_example']=combined
    B0=strain_matrix(pitch,0,0,0)
    for name,F in vectors.items():
      sol=np.zeros_like(F)
      sol[free]=solver.solve(F[free])
      uv=sol.reshape((-1,3))
      elem_u=sol[edofs]
      # From 3D stresses at centers of every solid element
      eps=elem_u@B0.T
      sigma=eps@D.T
      sx,sy,sz,txy,tyz,txz=sigma.T
      vm=np.sqrt(.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2)+3*(txy**2+tyz**2+txz**2))
      hubdisp=uv[hub].mean(axis=0)
      cases[name]={
       'hub_displacement_mm':[round(float(v),8) for v in hubdisp],
       'max_displacement_mm':round(float(np.linalg.norm(uv,axis=1).max()),7),
       'strain_energy_Nmm':round(float(.5*F@sol),8),
       'stress_vonMises_center_P95_MPa':round(float(np.quantile(vm,.95)),5),
       'stress_vonMises_center_max_MPa':round(float(vm.max()),5),
       'stress_vonMises_center_P99_MPa':round(float(np.quantile(vm,.99)),5),
      }
    return {
     'model':path.name,'voxel_size_mm':pitch,'elements':len(enodes),'nodes':len(xyz),
     'free_DOF':len(free),'clamped_nodes':len(fixed_nodes),'loaded_nodes':len(hub),
     'material_E_MPa':E,'material_poisson':nu,'assumed_loads':'Fz=+0.5N,Fy=-0.5tan(2deg)N,Mz=+1Nmm',
     'boundary_condition':'fuselage socket inner radial surface clamped (rigid bond)',
     'cases':cases,'duration_s':round(time.time()-t0,2)
    }

if __name__=='__main__':
 pitch=float(sys.argv[1]) if len(sys.argv)>1 else .7
 res=[]
 for variant in ('plate','V3'):
  for depth in (5,10):
   path=M/f'pukki_{variant}_{depth}mm_Z.stl'
   try:
    item=load_and_solve(path,pitch)
    res.append(item)
    print(path.name,item['elements'],item['duration_s'],item['cases']['combined_example'],flush=True)
   except Exception as e:
    print('ERROR',path.name,str(e),flush=True)
 out=OUT/f'solid_FEM_{str(pitch).replace(".","p")}mm.json'
 out.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 print('SAVED',out,flush=True)
