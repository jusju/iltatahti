# Potkuripukki V3 — V-tukien kiinnitys holkin takareunaan ja vahvistettu otsalevyn pidike

Päivitetty suunnittelumalli, 2026-11-01. Luonnonmukaista haarautumismallia **ei** tässä uudessa versiossa ole.

## Mitä muuttui suhteessa edelliseen V2-malliin

1. **Kaksi V-muotoista diagonaalia säilyvät** ja kantavat sekä aksiaalista kumivetoa että sivu- ja vääntökuormitusta. Muutettiin diagonaalien pään sijaintia, ei perusrakennetta.
2. **Pienemmän akseliholkin takareuna:** diagonaalin kärki siirrettiin lähemmäs runkoholkkiin päin osoittavaa akseliholkin reuna-aluetta: X=11,55 → X=10,70 mm (akseliholkin keskipiste X=12 mm; ulkosäde 1,70 mm). Molemmilla puolilla Y=±0,38 mm.
3. **Ison holkin reunaan ankkuroidut jalat:** suuremman holkin liitoskohtien keskipisteet ovat X=4,40 mm, Y=±2,85 mm; säde runkoakselista n. 5,24 mm. Runko-ontelon säde 5,10 mm ja ulkosäde 5,85 mm, joten molemmat Ø1,88 mm:n diagonaalien päät uppoavat **runkoholkin seinämän läpi** ja sulautuvat yhtenäiseksi tulostettavaksi kappaleeksi. Ontelo porataan uudestaan lopuksi. Z-liitos nostettiin 0,9×holkkisyvyydestä tasolle syvyys−0,45 mm lähelle kauempaa päätyreunaa.
4. **Otsalevyn tuki:** aiemmin 0,72 mm korkean pohjasillan korkeus/paksuus nostettiin **1,08 mm:iin** (1,5×). Pohjasillan leveys Y-suunnassa nostettiin **1,5-kertaiseksi**. X-ulottuvuus ja holkkien keskipisteiden etäisyys säilyvät entisinä.
5. **Muut mitat säilyvät:** runkoputki Ø10 mm, CAD-holkki Ø11,7/10,2 mm, keskipisteväli X=12 mm, potkuriakseli Ø0,8 mm (mallin reikä Ø0,95 mm), akselin 2° kallistus vasemmalle. Holkkisyvyyksille on edelleen 5/10 mm vaihtoehdot.

Geometrian pääasiallinen rakenne: holkit alkavat Z=0-tulostuspöytätasolta ja osoittavat ylös. Diagonaalit on mallinnettu kartiomaisina Ø1,52...1,88 mm tukina, kuten vanhassa versiossa. Kummankin V-haaran kiinnityskappale on tilavuusunionilla liitetty holkkirakenteeseen; yksikään irrallinen osa ei jää STL-malliin.

**'Takareuna' on tässä tulkittu molemmilla tavoilla:** pienessä akseliholkissa runkoon päin olevaksi reuna-alueeksi X-suunnassa, isossa runkoholkissa kauemmaksi Z-päätyreunaksi. Tämä on dokumentoitu lähdekoodin koordinaatein ja mallin 3D-esikatselussa.

## CAD-painoarviot

| Runkoholkin syvyys | V3, PLA | V3, PETG | Vertailulevy, PLA |
|---:|---:|---:|---:|
| 5 mm | 0,25867 g | 0,26493 g | 0,24181 g |
| 10 mm | 0,43364 g | 0,44413 g | 0,40871 g |

Laskettu CAD-tilavuudesta tiheyksin PLA 1,24 g/cm³ ja PETG 1,27 g/cm³. Ei sisällä liimaa, hiilikuitua, reunapurseita eikä mahdollisia slicerin lisämateriaaleja. Todellinen massa mitattava tulostetuista kappaleista.

## 3D-solid-FEM: täysin samat kuormat kuin V2:ssä

Käytössä sama `solid_fem.py`, jossa 8-solmuisia heksaedrisia voxel-tilavuuselementtejä, 3 vapausastetta/solmu ja isotrooppinen lineaari-elastinen materiaali E=2 000 MPa, ν=0,35. Koko kappale on mukana, ei yksittäinen palkki.

- Kumiveto **Fz = +0,500 N** (Z on tulostussuunnan akseli; oletettu voiman suunta). Tämä ei ole käyttäjältä mitattu vetojännitys.
- 2° vasemmalle vetävä sivuvoima **Fy = −0,5 tan(2°) = −0,01746 N**.
- **Mz = +1,0 N·mm** kiertomomentti potkuriakselin holkille.
- Yhdistetty kuorma näiden summana.
- Runkoholkin sisäseinämä on oletettu jäykästi kiinnitettyyn runkoputkeen.
- Koko FEM ajettu **0,75 mm** ja **0,50 mm** elementtikoolla sekä V3- että vertailulevymalleille. Alkuperäisten V2-mallien tallennetut FEM-tulokset ovat samojen kuormitusten vertailukohtana.

Tarkat tapauskohtaiset siirtymät, jännitysten P95/P99/maksimit, energia-arviot ja elementtimäärät: `laskenta/solid_FEM_0p5mm.json`, `laskenta/solid_FEM_0p75mm.json`. V2→V3-erot kummallakin verkkokoolla: `vertailu/FEM_V2_vs_V3.md` ja CSV.

**Huomio:** 0,50 ja 0,75 mm tulokset **eivät ole verkon suhteen konvergoituneita**. Erityisesti maksimijännitysten luvut voivat muuttua selvästi verkon mukana; oikea kuormankesto pitäisi osoittaa kerrosorientoidulla tarkemmalla FEM:llä ja fyysisellä testillä. V3:n aksiaalinen jäykkyys paranee 0,50 mm analyysissä, mutta samalla sivu- ja vääntövaste huononee. Tulos ei oikeuta julistamaan tätä rakenteellisesti parhaaksi kaikkien rasitusten osalta.

## Tulostettavuus

- Tulostuspöydällä molempien holkkien alapäät Z=0. Iso holkki pystyyn; pieni holkki myös pystyyn, akselireikä 2° kallellaan.
- Pohjasillan laajennus 1,5× Y- ja Z-suunnassa parantaa ensimmäisten kerrosten kontaktia.
- 10 mm:n mallin diagonaalikulma tulostuspöytään nähden on arviolta noin 51°, 5 mm:n noin 27°; etenkin 5 mm:n mallille tukimateriaali voi olla tarpeen. Näitä ei ole tarkistettu Bambu Studio -viipalointisimulaatiossa.
- Ø10,2 mm holkki ja Ø0,95 mm akselireikä ovat sovitusta varten ylimitoitettuja reikiä. Testaa käytännössä, mahdollisesti kalvaa jälkikäteen; varmista että akselireikä ei tukkeudu ja runkoputki mahtuu.
- FDM-PLA voi pettää kerrosrajasta, etenkin vinojen diagonaalien juuresta. Tee erillinen vetokoe, sivukuormakoe ja kiertokoe ennen käyttöä.

## Sisällys ja toistettavuus

- `mallit/pukki_V3_{5,10}mm_Z.stl` ja `.step` – uudet V-tuet.
- `mallit/pukki_plate_{5,10}mm_Z.stl` ja `.step` – uusilla 1,5× pohjasilloilla varustetut vertailulevymallit.
- `mallit/luo_mallit.py` – parametrinen, uudelleen ajettava CadQuery-lähdekoodi.
- `mallit/massa_ja_geometriatarkistus.json` sekä `mallit/painoarviot.csv` – CAD-tilavuus ja massat.
- `laskenta/solid_fem.py` sekä `laskenta/solid_FEM_*.json` – FEM-lähdekoodi ja laskenta.
- `vertailu/` – vanhat V2-tulokset, uudet vertailulaskelmat, kaaviot ja laskennan toistokoodi.
- `animaatio/pukki_V3_10mm_Z_xyz_hidas.mp4` – 12 sekuntia, 20 fps, hidas X/Y/Z-samanaikainen pyöritys, todellinen STL-geometria.
- `animaatio/esikatselu.png` – pysäytyskuva.
- `tekstit/` – tämä raportti, aiemman suunnittelupaketin saatavilla olleet keskustelutekstit ja yhteenveto.
- `aiemmat_paketit/potkuripukki_korjattu_V_kaikki_tiedostot.zip` – edellinen julkaistu suunnittelupaketti historiatiedostoineen.

**Workin koko alkuperäistä sanasta sanaan -transkriptiota ei voida taata; arkistossa on aiemmista luoduista paketeista palautetut tiedostot ja dokumentoidut yhteenvedot, ei sepitettyä Work-lokia.**
