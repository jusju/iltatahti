# Potkuripukki – korjattu kahden diagonaalin V-rakenne

**Versio:** 2026-11-01. Tässä versiossa ei ole luonnonmukaista rakennetta.

## Mitat ja tulostusasento

- Runkoputki Ø10 mm; seinämä 0,8 mm. Mallissa runkoholkki Ø11,7 mm, sisäreikä Ø10,2 mm (tulostusvälystä 0,2 mm halkaisijaan).
- Potkuriakseli Ø0,8 mm. Mallissa tulostettavan akseliholkin reiän säde on 0,475 mm (Ø0,95 mm); sovitus on testattava käytännössä.
- Holkkien akselien väli X-suunnassa 12 mm.
- Akselin kallistus Y-suuntaan 2° vasemmalle.
- Runkoholkin pituus 5 tai 10 mm.
- Z on tulostussuunta. Molemmat holkit alkavat pöytätasolta Z=0; otsalevyn minimaalinen pohjasilta yhdistää ne. Holkkien aukot ovat Z-suunnassa, joten ne eivät tarvitse umpinaista pohjatukea. Diagonaalien tuentarve on tarkistettava viipalointiohjelmassa.
- Kaksi V-diagonaalia lähtee akseliholkilta (z≈1,1 mm) ja kiinnittyy runkoholkkiin (z≈0,9×runkoholkin pituus). Niillä on merkittävä kumivedon Z-suuntainen kuormituskomponentti.
- Suunnittelukoodi mallintaa tämän täsmällisesti eikä ole topologiaoptimointialgoritmi.

## Massat, CAD-tilavuuden pohjalta

| Malli | PLA | PETG | CAD-tilavuus |
|---|---:|---:|---:|
| `pukki_plate_5mm_Z` | 0.2351 g | 0.2408 g | 189.6 mm³ |
| `pukki_V2_5mm_Z` | 0.2547 g | 0.2609 g | 205.4 mm³ |
| `pukki_plate_10mm_Z` | 0.4006 g | 0.4103 g | 323.1 mm³ |
| `pukki_V2_10mm_Z` | 0.4264 g | 0.4367 g | 343.9 mm³ |

PLA:n tiheyden oletus: 1,24 g/cm³; PETG 1,27 g/cm³. Painot eivät sisällä tulostuspurseen, pursotuksen poikkeamien, tukimateriaalin, liiman tai mahdollisten lisäosien painoa. Kaikki neljä STL-tiedostoa on todettu geometrisesti vesitiiviiksi ja yhtenäisiksi (`massa_ja_geometriatarkistus.json`).

## 3D-solid-FEM (voxelisoidut kahdeksansolmuiset heksaedrielementit)

**Kyllä, mukana on koko kappaleen 3D-tilavuuselementteihin perustuva lineaarinen FEM**. Kukin solmu sisältää kolme siirtymävapausastetta; käytetään isotrooppista kimmomateriaalia E=2000 MPa, Poisson=0,35. Laskenta on tehty 0,5 mm ja 0,75 mm voxelikoilla. Paksuudeltaan noin 1,5–1,9 mm diagonaalit ovat näin harvasti diskretoituja, joten tulosten numeerinen konvergenssi ei ole osoitettu. Tämä ei ole korkean tarkkuuden, tulostuskerrosten suunnan huomioiva lujuusvarmistus.

Kuormitusten **esimerkkioletukset** (eivät mitatut lennokin kuormat):
- +Z-suuntainen kumiveto 0,5 N.
- Vasemmalle -Y 0,5 × tan(2°) ≈ 0,01746 N.
- Kiertomomentti akselin Z-suunnan ympäri 1,0 N·mm.
- Yhdistetty tapaus kaikkien summasta.

Reunaehto: runkoputken holkin sisäpinnan solmut jäykästi kiinnitetty, mikä vastaa täydellisesti liimattua jäykkää runkoputkea. Todellisessa käytössä liitos voi joustaa tai murtua. Voiman jakautuma akseliholkissa on yksinkertaistettu. Akselin todelliset voiman/kierron suunnat voivat poiketa oletuksesta, ja 2° sivuvoima on mallinnettu erillisellä sivuvoimalla.

### 0,5 mm FEM-tulosvertailu

| Malli | Kumivedon holkkisiirtymä Z | Yhdistetyn kuorman suurin siirtymä | Yhdistetyn kuorman laskennallinen vm-maksimi |
|---|---:|---:|---:|
| `pukki_plate_5mm_Z.stl` | 0.002659 mm | 0.006770 mm | 0.758 MPa |
| `pukki_plate_10mm_Z.stl` | 0.001277 mm | 0.005837 mm | 0.619 MPa |
| `pukki_V2_5mm_Z.stl` | 0.002189 mm | 0.003378 mm | 0.563 MPa |
| `pukki_V2_10mm_Z.stl` | 0.000992 mm | 0.002138 mm | 0.489 MPa |

Tarkat FEM-tulokset, muut kuormitustapaukset, jännitysten prosenttipisteet, elementtimäärät ja 0,75 mm vertailu löytyvät laskennan JSON-tiedostoista. FEM-tulokset ovat laskennallisia eivätkä todista murtolujuutta. Suurin keskuspistejännitys ei ole todellinen geometrisen liitoksen huippujännitys.

## Optimoiminen ja rajoitukset

Kyse on **kuormituspolun perusteella suunnitellusta kahden diagonaalin V-rakenteesta**, ei todellisesta automaattisesta topologiaoptimoinnista. Varsinaista topologiaoptimointia ei tehty, koska sitä varten tarvittaisiin erillinen optimointisilmukka (esim. SIMP), valmistettavuusrajoitteet ja verkon konvergenssitestaus. Älä kutsu tätä automaattisen topologiaoptimoinnin tulokseksi.

Rakenne vaatii vielä käytännön tarkistukset: 0,4 mm suuttimen viipalointinäkymä, diagonaalien sillattavuus, tulostuskerrosten vaikutus, holkkien oikea mitta sekä liitoksen kuormituskoe. Tulostus ilman supportteja ei ole vielä vahvistettu viipaloinnilla. Erityisesti 5 mm mallin diagonaalien kulmat vaativat tarkastelua.

## Mitä tiedostot sisältävät

- `mallit/*.stl`: neljä tulostettavaa 3D-geometriaa, V- ja vertailulevymallit, 5/10 mm.
- `mallit/*.step`: samojen mallien muokattavat CAD-vientitiedostot.
- `mallit/luo_mallit.py`: parametrinen CadQuery-lähdekoodi.
- `mallit/painoarviot.csv`: painotaulukko.
- `mallit/massa_ja_geometriatarkistus.json`: alkuperäinen CAD-/STL-massojen tarkistus.
- `laskenta/solid_fem.py`: 3D-solid-FEM-lähdekoodi.
- `laskenta/solid_FEM_0p5mm.json` ja `solid_FEM_0p75mm.json`: mallikohtaiset tulokset.
- `laskenta/FEM_yhteenveto.csv`: tiivistetyt laskentatulokset.
- `animaatio/pukki_V_10mm_Z_xyz_hidas.mp4`: 12 sekunnin hidas kolmiakselinen pyöritys.
- `animaatio/render.py`: animaation lähdekoodi.
- `tekstit/*.md`: nykyinen raportti, historiatekstit ja suunnittelun yhteenveto.
- `aiemmat_paketit/*.zip`: aiempien kokeilujen alkuperäiset julkaistut paketit (mukana lähdehistoriaa, **eivät** uusin suositeltu geometria).

## Suositeltava kokeilu

Kokeile ensin `mallit/pukki_V2_10mm_Z.stl`. Valitse tulostuskerroksen suunta niin, että Z on ylöspäin; tarkista viipaloinnin esikatselussa diagonaalit ja koko pohjan kontaktipinta. Tee koevedot ennen lennättämistä. Älä perusta murtumiskestävyyttä numeeriseen FEM-arvioon ilman testejä.
