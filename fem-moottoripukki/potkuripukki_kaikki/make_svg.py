import numpy as np,trimesh
from scipy.spatial import ConvexHull
from pathlib import Path
m=trimesh.load(Path(__file__).parent/'pukki_V_10mm.stl',process=False)
V=np.asarray(m.vertices)
# silhouette and visible structural wireframe through a sparse point-cloud silhouette approximation
center=np.array([5.5,0.,5.]);V=V-center
# choose a reproducible subset of edges from the STL model
edges=np.asarray(m.edges_unique)
length=np.linalg.norm(V[edges[:,0]]-V[edges[:,1]],axis=1)
# select long edges, and systematic small edge samples to keep SVG lightweight
keep=np.flatnonzero(length>0.6)
if len(keep)<450:keep=np.unique(np.concatenate([keep,np.arange(0,len(edges),max(1,len(edges)//500))]))
else:keep=keep[::max(1,len(keep)//450)]
edges=edges[keep]
def rotate(axis,angle):
 c=np.cos(angle);s=np.sin(angle)
 if axis=='x':return np.array([[1,0,0],[0,c,-s],[0,s,c]])
 if axis=='y':return np.array([[c,0,s],[0,1,0],[-s,0,c]])
 return np.array([[c,-s,0],[s,c,0],[0,0,1]])
frames=[]
for ax in 'xyz':
 for j in range(12):
  r=rotate(ax,2*np.pi*j/12)@rotate('x',.35)@rotate('y',.35)
  p=V@r.T
  p2=p[:,:2]*17+np.array([205,165]);hull=ConvexHull(p2)
  path=' '.join(('M' if k==0 else 'L')+f'{p2[v,0]:.1f},{p2[v,1]:.1f}' for k,v in enumerate(hull.vertices))+' Z'
  lines=''.join(f'<path d="M{p2[a,0]:.1f},{p2[a,1]:.1f} L{p2[b,0]:.1f},{p2[b,1]:.1f}"/>' for a,b in edges)
  frames.append((ax,path,lines))
css='@keyframes cycle{0%,2.65%{opacity:1}2.85%,100%{opacity:0}}'
sv=['<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">',f'<style>{css}</style>','<rect width="700" height="400" fill="#101c2a"/><text x="28" y="36" fill="white" font-family="sans-serif" font-size="20">Indoor prop mount — V, 10 mm</text><text x="28" y="66" fill="#9ebbd1" font-family="sans-serif" font-size="13">3D projected animation: X → Y → Z, 360° each</text>']
for k,(ax,path,lines) in enumerate(frames):
 sv.append(f'<g style="animation:cycle 9s steps(1,end) infinite;animation-delay:-{k*.25:.3f}s;opacity:0">')
 sv.append(f'<path d="{path}" fill="#48b1c3" fill-opacity=".18" stroke="#50d0e6" stroke-width="1.5"/>')
 sv.append(f'<g fill="none" stroke="#7fcfe2" stroke-opacity=".32" stroke-width=".55">{lines}</g>')
 sv.append(f'<text x="500" y="65" fill="white" font-family="sans-serif" font-size="15">Rotation: {ax.upper()} axis</text></g>')
sv.append('<text x="28" y="378" fill="#a5b5c9" font-family="sans-serif" font-size="12">Illustrative STL projection; not a physical simulation</text></svg>')
(Path(__file__).parent/'pukki_V_10mm_pyöritys.svg').write_text(''.join(sv))
