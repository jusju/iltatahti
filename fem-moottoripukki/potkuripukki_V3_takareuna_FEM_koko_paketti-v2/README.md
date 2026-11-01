# Kumimoottorilennokin potkuripukki V3 — koko suunnittelupaketti

**Tämän version suositeltu kokeiltava malli:** `mallit/pukki_V3_10mm_Z.stl`.

Katso `tekstit/LUE_MINUT_V3.md` (rakenne, mitat, lujuusrajoitukset, massa, asennus), `vertailu/FEM_V2_vs_V3.md` (kaikki numeeriset erot) ja `animaatio/pukki_V3_10mm_Z_xyz_hidas.mp4` (mallin pyöritys).

Mallit on tehty CadQueryllä. Uusien mallien STL:t ovat yksiosaisia ja vesitiiviitä. FEM on 3D-solid-FEM, ei palkkiapproksimaatio, mutta perustuu heksaedrivoqueleihin ja karkeaan lineaariseen materiaaliin. **Todellista lujuutta tai supportitonta tulostusta ei ole sertifioitu.**

Toistaminen (esim. Linux, CADQuery, scipy, numpy, trimesh, vtk ja ffmpeg asennettuina):

```
python mallit/luo_mallit.py
python laskenta/solid_fem.py 0.75
python laskenta/solid_fem.py 0.5
python vertailu/laske_vertailu.py
python vertailu/piirra_vertailu.py
python animaatio/render.py
```

Edellisen V2-version raakatulokset löytyvät `vertailu/V2_lahdetiedot`-kansiosta. Alkuperäinen V2 ZIP sisältää myös aiemmat suunnitteluvaiheet ja tekstikoosteet.
