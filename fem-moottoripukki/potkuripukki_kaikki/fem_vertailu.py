"""2D Euler-Bernoulli frame FEM: explanatory screening model, NOT solid-mesh FEM.
Coordinates in X-Z plane, DOF per node u_x,u_z,rot_y. Sleeve boundary idealized fixed.
Loads 1 N axial Z and 1 Nmm bending moment around Y at bearing node.
"""
import numpy as np
E=2400.0 # N/mm2 assumed PLA, effective isotropic

def element(x1,z1,x2,z2,b,h):
    dx=x2-x1;dz=z2-z1;L=np.hypot(dx,dz);c=dx/L;s=dz/L
    A=b*h;I=b*h**3/12;ea=E*A/L;ei=E*I
    k=np.array([[ea,0,0,-ea,0,0],[0,12*ei/L**3,6*ei/L**2,0,-12*ei/L**3,6*ei/L**2],
       [0,6*ei/L**2,4*ei/L,0,-6*ei/L**2,2*ei/L],[-ea,0,0,ea,0,0],
       [0,-12*ei/L**3,-6*ei/L**2,0,12*ei/L**3,-6*ei/L**2],
       [0,6*ei/L**2,2*ei/L,0,-6*ei/L**2,4*ei/L]])
    T=np.zeros((6,6));R=np.array([[c,s,0],[-s,c,0],[0,0,1]]);T[:3,:3]=R;T[3:,3:]=R
    return T.T@k@T,L,A,I

def solve(kind,depth):
    if kind=='plate':
        nodes=[(5.9,1.5),(12.,1.5)]; elements=[(0,1,2.,3.)]; fixed=[0]
    else:
        nodes=[(5.9,.65),(5.9,depth-.65),(12.,1.5)];elements=[(0,2,1.65,1.65),(1,2,1.65,1.65)];fixed=[0,1]
    n=len(nodes);K=np.zeros((3*n,3*n)); lengths=[]
    for i,j,b,h in elements:
        k,L,A,I=element(*nodes[i],*nodes[j],b,h);lengths.append(L)
        dofs=[3*i,3*i+1,3*i+2,3*j,3*j+1,3*j+2]
        K[np.ix_(dofs,dofs)]+=k
    free=[i for i in range(3*n) if i//3 not in fixed];end=n-1
    out=[]
    for label,F in [('Fz_1N',(0.,1.,0.)),('Mx_1Nmm',(0.,0.,1.)),('Fx_1N',(1.,0.,0.))]:
        load=np.zeros(3*n);load[-3:]=F
        u=np.zeros(3*n);u[free]=np.linalg.solve(K[np.ix_(free,free)],load[free]);out.append((label,*u[-3:]))
    return out

print('Case,Load,ux_mm,uz_mm,rotation_rad')
for depth in [5,10]:
 for kind in ['plate','V']:
    for label,x,z,r in solve(kind,depth):print(f'{kind}_{depth},{label},{x:.6f},{z:.6f},{r:.6f}')
