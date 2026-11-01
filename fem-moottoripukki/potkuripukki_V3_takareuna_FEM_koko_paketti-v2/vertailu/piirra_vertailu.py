"""Plot the comparable 10mm 0.5 mm mesh V2-to-V3 changes for quick review."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
with (R/'FEM_V2_vs_V3_kaikki_kuormat.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
key=['Z-holkin siirtymä, kumiveto','Y-holkin siirtymä, 2° sivuveto','Y-holkin siirtymä, vääntö','Suurin siirtymä, yhdistelmä','Jännitys, yhdistelmä maksimi']
rows=[next(x for x in rows if x['pituus_mm']=='10' and x['verkkokoko_mm']=='0.5' and x['suure']==k) for k in key]
fig,ax=plt.subplots(figsize=(10.5,5.5),layout='constrained')
change=[float(r['muutos_prosenttia']) for r in rows]
ax.barh(range(len(change)),change)
ax.set_yticks(range(len(change)),key)
ax.invert_yaxis()
ax.axvline(0,linewidth=1,color='black')
for i,v in enumerate(change):ax.text(v+(1 if v>=0 else -1),i,f'{v:+.1f} %',va='center',ha='left' if v>=0 else 'right')
ax.set_xlim(min(change)-17,max(change)+20)
ax.set_xlabel('Uusi V3 suhteessa vanhaan V2 (%)')
ax.set_title('10 mm pukkimalli — 0,50 mm voxel-FEM, samat kuormat')
ax.grid(axis='x',alpha=.2)
fig.savefig(R/'V2_V3_10mm_FEM_muutos.png',dpi=160)
print('wrote chart')
