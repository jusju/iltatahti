# Suunnittelun historia ja käyttörajoitukset

## Käyttäjän korjaus (2026-11-01)

"Tämä uusin malli ei voi lujuusopillisesti toimia, sillä kaikkein suurimpaan suuntaan eli mihin kumi vetää holkin päätä ei ole diagonaalitukea. Tee kaikki uudestaan muuten samalla tavalla ja unohda luonnonmukainen malli. Diagonaalitukia piti olla kaksi V-muodossa kuten ennen. Ainoastaan pukin otsalevy oli tarkoitus optimoida tulostuksen suhteen, muuten säilytetään edellisen version piirteet. Laita mp4 animaatio mukaan myös luotuun taas uuteen zippiin. Laita painoarviot zippiin. Pystytköhän tekemään koko 3D kappaleen solid-FEM ja todellisen topologiaoptimoinnin myös? Nyt meni lujuusopillisesti ainakin väärin, että vaikuttavia voimia ei otettu huomioon - lähinnä veto ja kierto sekä poikittaisrasitus, kun putki vetää 2 astetta vasemmalle."

## Korjauspäätös

- V-tuen on kannettava +Z-suuntainen kumiveto, ei vain sivuttaisvoima.
- Yhden diagonaalin tai vain vaakatasossa olevan V-tuen sijasta käytetään kahta viistoon nousevaa diagonaalia.
- Otsalevy optimoidaan Z-suuntaista 3D-tulostusta varten.
- Luonnonmukaista mallia ei jatkokehitetä.
- Vertailulevymallit säilytetään ainoastaan vertailukäyttöä varten.
- Pakettiin sisällytetään CAD, STL, MP4, painot sekä 3D-solid-FEM-laskennan lähdekoodi ja tulokset.

## Aiemmat suunnittelukierrokset

Historialliset raportit sisältävät aikaisempien välimallien massat ja simulaatiot; vanhat numerot eivät ole yhteismitallisia uuden geometrian kanssa. Aiemmat ZIP-paketit säilytetään historiassa eikä niitä tule sekoittaa uusiin STL:iin.

Täydellistä Work-keskustelun alkuperäistekstiä ei ole käytettävissä. `tekstit/aiemmat_assistentin_vastaukset.md` ja `tekstit/keskustelu_ja_rajoitukset.md` ovat aiemman julkaisun dokumentointia ja sisältävät tiivistelmiä, eivät täydellistä sanasta sanaan -transkriptiota.
