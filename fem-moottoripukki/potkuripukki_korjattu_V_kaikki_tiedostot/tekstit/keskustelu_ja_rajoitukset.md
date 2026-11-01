# Potkuripukin suunnittelukeskustelun sisältö 1.11.2026

## Käyttäjän tässä keskustelussa esittämät pyynnöt (sanatarkasti)

> äsken laskit minulle fem analyysiä pukista yms. kaikki jäi kesken, kun work tilauksessa ei kuulemma tilaa. voitko laskea kaiken uudestaan täällä chätissä?

> Ajattelin kolmiot kyllä 90 astetta eri suunnassa eli sivusuunnassa. Voisitko tehdä tuosta generative design henkisen luonnon muotoija mukaelevan kaikken parhaan keveys ja lujuus ominaisuuksiltaan? Talleta koko suunnittelupaketti zip:iin, kaikki mitä tulostit tähän näytölle ja mp4 animaatio miltä pukki näyttää pyöriteltynä x, y ja z akselien ympäri hitaasti kaikkia yhtäaikaa.

> Joo ala tuottamaan kaikki

> Teetkö nyt jotain?

> Voisitko luoda kaiken vielä uudestaan ja sisällyttää suunnittelupakettiin kaiken chättiin ja workkiin kirjoittamasi asiaan liittyvän tekstin md-muodossa? Muokkaa suunnitelmaa niin, että se on helpompi 3D tulostaa eli että se tulostetaan ikäänkuin runkoputki osoittaen suoraan zeniittiin ylöspäin. Tällöin yksi moottoriakselin holkista pitää vastata tulostuspöytään, jotta tulostaminen on helpomaa ja itse putki eli holkkirakenne ei vaadi tulostuakseen support rakenteita. Tee uusi zip-tiedosto ihan kaikesta.

## Saatavilla ollut vanha dokumentaatio
Aiemman suunnittelun täydellinen `LUE_MINUT.md`, aiemmat mallit ja laskentakoodi ovat säilytettyinä edellisissä ZIP-paketeissa kansiossa `alkuperaiset_paketit/`. Niissä ovat aiemmin tuotetut mallikohtaiset massat ja palkki-FEM-tulokset sekä MP4.

## Aiempien Work-vaiheiden palautettavat yhteenvedot — ei sanasta sanaan transkriptio
- Runkoputki Ø10 mm, seinämä 0,8 mm; potkuriakseli Ø0,8 mm; tulostimen suutin 0,4 mm.
- Pyyntö tehdä 5 mm:n putken sisäänmenovaihtoehto ja koko kappaleen FEM, sekä Build123d/OpenSCAD, STL ja pyöritys-SVG.
- Pyyntö verrata yhden levytuen jäykkyyttä V-muotoiseen tukeen; käyttäjä myöhemmin täsmensi V-tuen sivuttaissuunnan.
- Aiempi työ käytti palkki-FEM-arviota, ei validoitua 3D-solid-FEM:iä. Topologiaoptimointia ei ollut suoritettu.
- Work-keskustelun täydellistä alkuperäistä tekstiä ei ollut saatavissa tässä istunnossa. Emme väitä näitä yhteenvetoja alkuperäisiksi sitaateiksi.

## Viittaus aiemmin keskustelussa esitettyihin tuloksiin
10 mm:n aiemmassa mallissa massat olivat noin 0,433 g (levy), 0,430 g (sivuttais-V), 0,455 g (bio). Alkuperäinen rajattu palkkimalli ennusti sivuttais-V:n Y-kuormituksen jäykkyyden olevan noin 5,3-kertainen levyyn nähden, mutta heikomman pystysuunnassa. Nämä luvut eivät ole uuden Z-geometrian FEM-tuloksia.
