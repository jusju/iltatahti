# FEM-vertailu: vanha V2 ja uusi V3

Päävertailu koskee **samoja 3D-voxel-heksaelementti-FEM-kuormia, materiaalia ja reunaehtoja**. Muutosprosentti = (uusi/vanha−1)×100 %. Negatiivinen tarkoittaa pienempää siirtymää/jännitystä, mutta **suurimman voxel-keskipistejännityksen vertailua ei pidä tulkita lujuustodistukseksi**.

Kuormat: Fz=+0,5 N; Fy=−0,5 tan(2°) ≈ −0,01746 N; Mz=1 N·mm. PLA: E=2000 MPa, ν=0,35. Kiinnitys: jäykkä liitos runkoputken holkin sisäpinnalle.

## Painon muutos

| Runkoholkin syvyys | V2 PLA | V3 PLA | Muutos | V3 PETG |
|---|---:|---:|---:|---:|
| 5 mm | 0.25470 g | 0.25867 g | +1.56 % | 0.26493 g |
| 10 mm | 0.42640 g | 0.43364 g | +1.70 % | 0.44413 g |

## 0.5 mm verkko

| Syvyys | Kuormitus / suure | V2 | V3 | Muutos |
|---|---|---:|---:|---:|
| 5 mm | Z-holkin siirtymä, kumiveto (mm) | 0.002189 | 0.001716 | -21.6 % |
| 5 mm | Y-holkin siirtymä, 2° sivuveto (mm) | 0.000053 | 0.000067 | +25.7 % |
| 5 mm | Y-holkin siirtymä, vääntö (mm) | 0.000520 | 0.000661 | +27.1 % |
| 5 mm | Suurin siirtymä, yhdistelmä (mm) | 0.003378 | 0.003134 | -7.2 % |
| 5 mm | Jännitys, yhdistelmä P95 (MPa) | 0.1825 | 0.1790 | -2.0 % |
| 5 mm | Jännitys, yhdistelmä maksimi (MPa) | 0.5628 | 0.4349 | -22.7 % |
| 5 mm | Muodonmuutosenergia, yhdistelmä (Nmm) | 0.0006613 | 0.0005524 | -16.5 % |
| 10 mm | Z-holkin siirtymä, kumiveto (mm) | 0.000992 | 0.000797 | -19.6 % |
| 10 mm | Y-holkin siirtymä, 2° sivuveto (mm) | 0.000075 | 0.000093 | +24.7 % |
| 10 mm | Y-holkin siirtymä, vääntö (mm) | 0.000808 | 0.001073 | +32.9 % |
| 10 mm | Suurin siirtymä, yhdistelmä (mm) | 0.002138 | 0.002168 | +1.4 % |
| 10 mm | Jännitys, yhdistelmä P95 (MPa) | 0.1156 | 0.1082 | -6.4 % |
| 10 mm | Jännitys, yhdistelmä maksimi (MPa) | 0.4887 | 0.3441 | -29.6 % |
| 10 mm | Muodonmuutosenergia, yhdistelmä (Nmm) | 0.0004194 | 0.0003587 | -14.5 % |

## 0.75 mm verkko

| Syvyys | Kuormitus / suure | V2 | V3 | Muutos |
|---|---|---:|---:|---:|
| 5 mm | Z-holkin siirtymä, kumiveto (mm) | 0.001475 | 0.001630 | +10.5 % |
| 5 mm | Y-holkin siirtymä, 2° sivuveto (mm) | 0.000040 | 0.000050 | +24.3 % |
| 5 mm | Y-holkin siirtymä, vääntö (mm) | 0.000386 | 0.000540 | +40.0 % |
| 5 mm | Suurin siirtymä, yhdistelmä (mm) | 0.002340 | 0.002766 | +18.2 % |
| 5 mm | Jännitys, yhdistelmä P95 (MPa) | 0.1318 | 0.1389 | +5.4 % |
| 5 mm | Jännitys, yhdistelmä maksimi (MPa) | 0.2434 | 0.2896 | +19.0 % |
| 5 mm | Muodonmuutosenergia, yhdistelmä (Nmm) | 0.0004394 | 0.0004955 | +12.8 % |
| 10 mm | Z-holkin siirtymä, kumiveto (mm) | 0.000680 | 0.000640 | -6.0 % |
| 10 mm | Y-holkin siirtymä, 2° sivuveto (mm) | 0.000055 | 0.000052 | -5.5 % |
| 10 mm | Y-holkin siirtymä, vääntö (mm) | 0.000560 | 0.000552 | -1.4 % |
| 10 mm | Suurin siirtymä, yhdistelmä (mm) | 0.001341 | 0.001283 | -4.3 % |
| 10 mm | Jännitys, yhdistelmä P95 (MPa) | 0.0808 | 0.0776 | -4.0 % |
| 10 mm | Jännitys, yhdistelmä maksimi (MPa) | 0.2316 | 0.2220 | -4.2 % |
| 10 mm | Muodonmuutosenergia, yhdistelmä (Nmm) | 0.0002583 | 0.0002417 | -6.4 % |

## Tulkintarajat

- FEM-analyysi on **tilavuuselementteihin perustuva 3D-solid-FEM**, mutta geometria voxelisoidaan eikä elementtiverkko seuraa kaarevia pintoja tarkasti.
- Tulosten verkkoherkkyys on huomattava, erityisesti jännityksissä. 0,5 mm ja 0,75 mm eivät ole osoitetusti konvergoituneita.
- PLA oletetaan isotrooppiseksi; FDM:n kerrosrajat, todellinen täyttö, liimaus ja viruminen puuttuvat.
- V3:n kumivedon jäykkyys voi parantua, mutta kierron vaste voi samalla heiketä. V3:a ei pidä väittää kaikissa kuormissa vahvemmaksi.
- Holkkien mitat ja metallisen 0,8 mm akselin tulostusvälys pitää sovittaa käytännössä.
