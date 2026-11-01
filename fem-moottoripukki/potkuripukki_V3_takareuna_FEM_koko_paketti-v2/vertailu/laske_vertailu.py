"""Compare V2 vs V3 FEM results without recomputing old files.
Reference old result files come from saved prior design package.
"""
from pathlib import Path
import json, csv, math
ROOT=Path(__file__).resolve().parent.parent
OLD=ROOT/'vertailu'/'V2_lahdetiedot'
NEW=ROOT
METRICS=[
 ('rubber_Fz_0p5N','hub_displacement_mm',2,'Z-holkin siirtymä, kumiveto','mm'),
 ('left_Fy_2deg','hub_displacement_mm',1,'Y-holkin siirtymä, 2° sivuveto','mm'),
 ('shaft_torsion_Mz_1Nmm','hub_displacement_mm',1,'Y-holkin siirtymä, vääntö','mm'),
 ('combined_example','max_displacement_mm',None,'Suurin siirtymä, yhdistelmä','mm'),
 ('combined_example','stress_vonMises_center_P95_MPa',None,'Jännitys, yhdistelmä P95','MPa'),
 ('combined_example','stress_vonMises_center_max_MPa',None,'Jännitys, yhdistelmä maksimi','MPa'),
 ('combined_example','strain_energy_Nmm',None,'Muodonmuutosenergia, yhdistelmä','Nmm'),
]
rows=[]
for pitch in ('0p5','0p75'):
 old=json.loads((OLD/f'solid_FEM_{pitch}mm.json').read_text())
 new=json.loads((NEW/'laskenta'/f'solid_FEM_{pitch}mm.json').read_text())
 for depth in (5,10):
  a=next(x for x in old if x['model']==f'pukki_V2_{depth}mm_Z.stl')
  b=next(x for x in new if x['model']==f'pukki_V3_{depth}mm_Z.stl')
  for name,key,idx,desc,unit in METRICS:
   v1=a['cases'][name][key];v2=b['cases'][name][key]
   if idx is not None:v1=v1[idx];v2=v2[idx]
   # Magnitude ratios for signed displacement metrics
   value_old=abs(v1) if idx is not None else v1
   value_new=abs(v2) if idx is not None else v2
   pct=100*(value_new/value_old-1) if value_old else float('nan')
   rows.append(dict(verkkokoko_mm=pitch.replace('p','.'),pituus_mm=depth,
     suure=desc,yksikko=unit,vanha_V2=value_old,uusi_V3=value_new,
     muutos_prosenttia=round(pct,2),elementit_V2=a['elements'],elementit_V3=b['elements']))
with (ROOT/'vertailu'/'FEM_V2_vs_V3_kaikki_kuormat.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
old_mass={x['name']:x for x in json.loads((OLD/'massa_ja_geometriatarkistus.json').read_text())}
new_mass={x['name']:x for x in json.loads((NEW/'mallit/massa_ja_geometriatarkistus.json').read_text())}
masses=[]
for d in (5,10):
 a=old_mass[f'pukki_V2_{d}mm_Z'];b=new_mass[f'pukki_V3_{d}mm_Z'];
 masses.append(dict(pituus_mm=d,vanha_PLA_g=a['PLA_g'],uusi_PLA_g=b['PLA_g'],
     PLA_muutos_prosenttia=round(100*(b['PLA_g']/a['PLA_g']-1),2),
     vanha_PETG_g=a['PETG_g'],uusi_PETG_g=b['PETG_g'],
     vanha_tilavuus_mm3=a['volume_mm3'],uusi_tilavuus_mm3=b['volume_mm3']))
with (ROOT/'vertailu'/'paino_V2_vs_V3.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=masses[0].keys());w.writeheader();w.writerows(masses)

def f(x,n=6):return f'{x:.{n}f}'
md=['# FEM-vertailu: vanha V2 ja uusi V3','',
'Päävertailu koskee **samoja 3D-voxel-heksaelementti-FEM-kuormia, materiaalia ja reunaehtoja**. Muutosprosentti = (uusi/vanha−1)×100 %. Negatiivinen tarkoittaa pienempää siirtymää/jännitystä, mutta **suurimman voxel-keskipistejännityksen vertailua ei pidä tulkita lujuustodistukseksi**.','',
'Kuormat: Fz=+0,5 N; Fy=−0,5 tan(2°) ≈ −0,01746 N; Mz=1 N·mm. PLA: E=2000 MPa, ν=0,35. Kiinnitys: jäykkä liitos runkoputken holkin sisäpinnalle.','',
'## Painon muutos', '', '| Runkoholkin syvyys | V2 PLA | V3 PLA | Muutos | V3 PETG |','|---|---:|---:|---:|---:|']
for a in masses:
 md.append(f"| {a['pituus_mm']} mm | {a['vanha_PLA_g']:.5f} g | {a['uusi_PLA_g']:.5f} g | {a['PLA_muutos_prosenttia']:+.2f} % | {a['uusi_PETG_g']:.5f} g |")
for p in ('0.5','0.75'):
 md.extend(['',f'## {p} mm verkko','', '| Syvyys | Kuormitus / suure | V2 | V3 | Muutos |', '|---|---|---:|---:|---:|'])
 for a in rows:
  if a['verkkokoko_mm']!=p:continue
  if a['yksikko']=='mm': prec=6
  elif a['yksikko']=='MPa':prec=4
  else:prec=7
  md.append(f"| {a['pituus_mm']} mm | {a['suure']} ({a['yksikko']}) | {a['vanha_V2']:.{prec}f} | {a['uusi_V3']:.{prec}f} | {a['muutos_prosenttia']:+.1f} % |")
md.extend(['','## Tulkintarajat','',
'- FEM-analyysi on **tilavuuselementteihin perustuva 3D-solid-FEM**, mutta geometria voxelisoidaan eikä elementtiverkko seuraa kaarevia pintoja tarkasti.','- Tulosten verkkoherkkyys on huomattava, erityisesti jännityksissä. 0,5 mm ja 0,75 mm eivät ole osoitetusti konvergoituneita.',
'- PLA oletetaan isotrooppiseksi; FDM:n kerrosrajat, todellinen täyttö, liimaus ja viruminen puuttuvat.',
'- V3:n kumivedon jäykkyys voi parantua, mutta kierron vaste voi samalla heiketä. V3:a ei pidä väittää kaikissa kuormissa vahvemmaksi.',
'- Holkkien mitat ja metallisen 0,8 mm akselin tulostusvälys pitää sovittaa käytännössä.',
''])
(ROOT/'vertailu'/'FEM_V2_vs_V3.md').write_text('\n'.join(md),encoding='utf-8')
print('\n'.join(md[:24]))
