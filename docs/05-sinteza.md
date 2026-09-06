# AquaCell — sinteza: poslovni model, algoritmi, simulacija, rezultati

Stanje na 30.08.2026. Zamjenjuje sve prethodne dokumente gdje su u konfliktu.
Izvorni plan je u `00-source-brief.md`, kritička recenzija u `01`–`03`, registar
odluka u `04`. Ovaj dokument je jedini koji sadrži **izmjerene** rezultate.

Sve brojke su iz simulacije s **procijenjenim** profilima potrošnje, ne iz
mjerenja na hrvatskim domaćinstvima. Točan status pouzdanosti svake brojke je u
poglavlju 9.

---

## 1. Sažetak

**Proizvod nije ono što je izvorni plan pretpostavljao.** Plan je bio okrenut na
smanjenje potrošnje (redukciju) za aFRR i mFRR. Simulacija pokazuje da je
**preuzimanje viška energije (apsorpcija) dvostruko do trostruko veći proizvod**,
s manjim rizikom i bez ikakvog utjecaja na komfor korisnika.

Za flotu od 5000 bojlera, pošteno i u megavatima:

```
noćna apsorpcija     00–05      1,7 – 2,8 MW
solarna apsorpcija   10–16      1,0 – 1,6 MW
jutarnja redukcija   06–09      0,8 – 1,2 MW
večernja redukcija   17–21      0,7 – 1,1 MW
```

Za 1 MW noćne apsorpcije treba **oko 2.400 uređaja**. Za 1 MW jutarnje redukcije
s ikakvom marginom treba **7.000–8.000**. To je trostruka razlika u trošku
akvizicije za isti megavat.

Tri nalaza koja mijenjaju plan:

1. **Nije moguće nuditi simetričan proizvod kroz cijeli dan.** Redukcija varira
   od 0,23 do 2,04 MW kroz dan — faktor devet. Ponude moraju biti vezane na sat.
2. **Flota iznad ~1000 uređaja ne postaje pouzdanija**, samo veća. Haircut od
   22–24 % je strukturan i ostaje zauvijek.
3. **Garancije nisu moguće.** Ponuda mora biti vjerojatnosna s eksplicitnom
   razinom rizika. Interval observer koji daje tvrde granice je pogrešan alat za
   tržište, i ostaje samo za zaštitu komfora.

---

## 2. Poslovni model

### 2.1 Što se prodaje

| Proizvod | Smjer | Rizik ako pogriješiš | Utjecaj na korisnika |
|---|---|---|---|
| Apsorpcija | trošiti na poziv | samo kazna za neisporuku | **nikakav** — ima pun bojler |
| Redukcija | ne trošiti na poziv | kazna **i** hladan tuš | odlazak korisnika |

Ta asimetrija je odlučujuća. Kod apsorpcije je najgori ishod poznat, ograničen i
novčan. Kod redukcije je najgori ishod izgubljen korisnik, što nije poolabilno
niti ograničeno.

Zato apsorpcija ide prva, i zato smije voziti agresivnije.

### 2.2 Redoslijed faza, revidiran

**Faza 0 — jedan uređaj, Prečko.** Provjera mehanike: gdje sonda termostata
mjeri, javljaju li se sidra, koliko je stvarni `L`, `E_hyst` i kapacitet. Ne
proizvodi zaključke o poslu. Ako je bojler 30 l, on je za mjerenje fleksibilnosti
bezvrijedan (vidi 8.4) ali za provjeru mehanike savršen.

**Faza 1 — 100 uređaja.** Nula prihoda, i to treba pisati u planu. Sto uređaja
je 0,2 MW nazivno i oko 20 kW poštene apsorpcije — dva reda veličine ispod
minimalne ponude. Svrha je isključivo: stvarni profili potrošnje, validacija
estimatora, i mjerenje stope hladnih tuševa.

**Faza 2 — 2.400 uređaja, noćna apsorpcija.** Prvi megavat i prvi prihod. Ovo je
najkraći put koji podaci pokazuju.

**Faza 3 — 5.000+ uređaja, dodavanje redukcije.** Redukcija zahtijeva
tri puta više uređaja za isti megavat i nosi rizik komfora, pa ide kasnije.

### 2.3 Prihod po uređaju

Nije mjereno. Poznati red veličine iz recenzije: **40–150 €/uređaj/godinu bruto**
od kapaciteta i arbitraže zajedno. Mora se zamijeniti stvarnim cijenama s HOPS
tendera prije ikakvog financijskog modela.

Protiv toga: ~30 € hardvera (Shelly + DIN kontaktor), 40–80 € električara,
10–20 €/god platforme i podrške.

**Dominantan trošak nije senzor nego električar.** Uklanjanje termistora od 150 €
je drugorazredni problem; ugradnja od 60 € je prvorazredni. Prava poluga je
kanal: ugradnja pri zamjeni bojlera, kad je električar ionako tamo i plaćen.

### 2.4 Ponuda korisniku

Dan-unaprijed arbitraža **ne daje uštedu** hrvatskom domaćinstvu na reguliranoj
dvotarifnoj mjeri, jer cjenovni signal do njega ne dolazi, a noćnu arbitražu mu
već radi besplatni mehanički kontaktor.

Poštena ponuda je **udio u prihodu od balansiranja**: besplatan hardver, fiksna
godišnja naknada, garancija tople vode. To je provjerljivo i ne ovisi o reformi
tarifa.

### 2.5 Regulatorni blokeri

Neriješeno, i sve blokira:

- Zahtijeva li HOPS ovjerena mjerila? Ako da, strategija s relejem od 15 € pada,
  jer Shelly nije ovjereno mjerilo, sat mu nije NTP-točan, a telemetrija ide
  preko potrošačkog WiFi-ja. **Tiko je izgradio K-Box točno zbog toga.**
- Postoje li dinamičke tarife za domaćinstva u Hrvatskoj?
- Ugovor s dobavljačem (BRP) za obračun neravnoteže.
- Stvarne cijene na tenderima.

**Zaobilaznica koja skida sve to s kritičnog puta:** prodaja fleksibilnosti u
portfelj postojećeg prekvalificiranog BSP-a. Oni imaju mjerila i odobrenja, ti
imaš uređaje. Prihod pri 500 uređaja umjesto 2.400, i pitanje ovjerenih mjerila
postaje njihov problem.

### 2.6 Legionela

Optimizator namjerno drži vodu hladnijom, i donja granica komfora (~40 °C) je
optimum rasta bakterije. To je uvjet koji stvaraš ti, namjerno, na tisućama
spremnika.

Rješenje: **dnevno grijanje do isklopa termostata.** Ako je termostat na ≥60 °C,
to daje termičku dozu sedam puta češće od preporuke norme, i profil rada je
identičan toplinskoj pumpi za sanitarnu vodu ili solarnom bojleru — dakle
propisan i prihvaćen.

Uvjet: **električar pri montaži postavi i zapiše termostat na ≥60 °C.** Bez toga
je ciklus nedokaziv, jer isklop dokazuje samo da si došao do onoga na što je
kotačić postavljen, a temperaturu ne mjeriš.

Iznad 60 °C se ne ide: kamenac se izlučuje znatno brže, a bilanca kapaciteta
protiv dodatnog gubitka je približno nula (+930 Wh pufera protiv +15 W trajnog
gubitka ≈ 10 €/god u oba smjera).

U marketingu se ne tvrdi dezinfekcija. Tvrdnja je: *„naša kontrola ne smanjuje
izloženost spremnika visokoj temperaturi ispod onoga što bi bilo bez nas"* — to
je mjerljivo i dokazivo brojanjem isklopa.

---

## 3. Fizički sustav i što je uopće vidljivo

### 3.1 Topologija

Shelly relej je u seriji **prije** mehaničkog termostata. Struja teče samo ako su
oba zatvorena:

```
P > 0   ⟺   relej zatvoren  ∧  termostat zatvoren
```

Iz toga slijedi cijela informacijska struktura sustava:

| Stanje releja | Što vidiš o termostatu |
|---|---|
| zatvoren | **sve** — snaga je posredni prekidač njegovog stanja |
| otvoren | **ništa** — struja je nula u oba slučaja |

**To je temeljno ograničenje arhitekture:** slijep si točno onda kad zarađuješ,
jer redukcija znači otvoren relej.

### 3.2 Referentni bojler

Sve brojke u dokumentu koriste ovaj uređaj gdje nije drugačije navedeno:

```
volumen            80 l
toplinski kapacitet C = 80 × 1,163 = 93 Wh/K
grijač             2000 W
termostat          60 °C, histereza 8 K
okolina            22 °C (grijana kupaonica)
dovodna voda       8 °C zima / 18 °C ljeto
granica komfora    40 °C
```

Izvedeno:

```
E_hyst             8 K × 93 = 744 Wh    = 22 min grijanja
gubitak L          1,47 W/K × 34 K = 50 W = 1,2 kWh/dan
prazna pauza       744 / 50 = 14,9 h
kapacitet zima     93 × (60 − 8) = 4838 Wh
kapacitet ljeto    93 × (60 − 18) = 3908 Wh
jedan tuš zima     40 l × 1,163 × (40 − 8) = 1489 Wh
jedan tuš ljeto    40 l × 1,163 × (40 − 18) = 1023 Wh
radni ciklus       ~17 % (350 W prosjek od 2043 W nazivno)
```

Dvije brojke koje treba imati u glavi:

**Prazna pauza je 15 sati.** Zato se `L` ne može mjeriti svaku noć — domaćinstvo
nikad ne provede 15 sati bez tople vode osim kad nikoga nema.

**Histerezni pojas je 40 % korisnog kapaciteta** (744 / 1860 Wh iznad granice
komfora). Mehanički termostat sam od sebe već šeta spremnik kroz veliki dio
raspona koji prodaješ; tvoja dodana vrijednost je više u **trenutku** nego u
količini.

---

## 4. Šest kalibriranih veličina

Sve u vatima i vatsatima. **Nijedna temperatura se nigdje ne pojavljuje**, jer
bez senzora ništa nije izrazivo u stupnjevima — ni histereza, jer za nju treba
efektivni volumen koji nije nazivni.

| Ime | Što je | Kako se dobiva | Latencija |
|---|---|---|---|
| `E_stored` / `d` | trenutno stanje, kao manjak ispod isklopa | integrator + sidra | trenutno |
| `E_capacity` | energija punog spremnika | forsirana kalibracijska noć | dani do tjedan |
| `E_hyst` | pojas histereze termostata | jedno grijanje uklop→isklop | ~1 dan |
| `L` | gubitak kroz izolaciju | p2 gubitka kroz duge cikluse | **tjedni do prvog odmora** |
| `E_reserve` | koliko se mora čuvati za komfor | p90 vlastite potrošnje | tjedni |
| `band` | prodajni pojas | kalibracijska noć | dani do tjedan |

### 4.1 Zašto energija a ne temperatura

Izvorna jednadžba `SoC_{k+1} = α·SoC_k + β·P_k − γ·D_k − L_k` nije valjana
diskretizacija. Član `α·SoC` pretpostavlja da je gubitak proporcionalan razlici
prema **granici komfora**, a fizički je proporcionalan razlici prema
**prostoriji**. To se izjednačava samo ako je `T_amb = T_min`, što nikad nije.

Dublji razlog: iz podataka o snazi se `UA` i `C` **ne mogu razdvojiti**. Hlađenje
daje `τ = C/UA`, grijanje daje `C/η`. Izlaz je samo taj što je `η ≈ 1` za uronjeni
otporni grijač.

U energetskim jedinicama taj problem ne postoji, jer je svaka opažljiva veličina
energija ili trajanje.

### 4.2 Zašto manjak a ne apsolutno stanje

Stanje se prati kao **manjak ispod točke isklopa**, `d`, u Wh. `d = 0` znači da je
termostat upravo isklopio.

Time apsolutna skala u potpunosti ispada. Ne treba znati koliko vode je ispod
sonde termostata, ne treba `E_capacity` u jednadžbi stanja, i sidro na isklopu je
egzaktno i besplatno.

### 4.3 Sezonska ovisnost — što se mijenja s čime

| Uzrok | `E_capacity` | `E_hyst` | `L` | `E_reserve` |
|---|---|---|---|---|
| temperatura prostorije | — | — | ±10 % grijano, ±50 % negrijano | — |
| temperatura dovodne vode | +24 % zimi | — | — | +46 % zimi |
| korisnik zavrne kotačić +10 K | +19 % | ~— | +25 % | — |
| kamenac (godine) | polagano pada | polagano pada | ~— | — |
| zamijenjen termostat | ovisi | **skok** | ovisi | — |
| promjena u domaćinstvu | — | — | — | **skok** |
| kapa topla voda | — | — | **skok, trajan** | — |

Svaki uzrok ima jedinstven potpis. To je jedini način razlikovanja bez senzora.

Dvije korisne ortogonalnosti:

**`E_reserve` je imun na kotačić.** Energija koju potrošnja odnese je
`V × 1,163 × (T_slavina − T_mreža)` — temperatura spremnika se ne pojavljuje. Da
dostaviš 40 l na 40 °C, uložiš istih 1489 Wh bez obzira grije li spremnik na 60
ili 70. Statistika navika ostaje valjana pri promjeni kotačića.

**`E_hyst` je imun na kotačić.** Širina histereze je svojstvo bimetala; oba se
ruba pomaknu jednako.

**Zašto je +46 % veće od +24 % za isti pomak od 10 K:** dijeli se s različitim
rasponom. Temperatura slavine (40 °C) je blizu mreže, pa je 10 K veliki dio te
razlike; temperatura isklopa (60 °C) je daleko, pa je isti pomak proporcionalno
manji. Posljedica: **zimi rezerva raste brže od kapaciteta**, pa udio spremnika
koji moraš zadržati raste s 26 % na 31 %. Zima stišće proizvod s obje strane, a
upravo je zima kad je balansiranje najvrjednije.

### 4.4 Sezona se ne predviđa, nego mjeri

Prognoza vremena nije potrebna i ne bi pomogla:

- `L` je direktno vidljiv, u vatima. Prognoza bi dala procjenu ulazne veličine iz
  koje bi računao ono što već imaš.
- Vanjska temperatura je slab pokazatelj temperature grijane kupaonice — te dvije
  stvari su namjerno odspojene.
- Uvela bi vanjsku zavisnost bez koristi.
- Najgore: **mislio bi da znaš.** Izmjereni `L` te ne može zavarati jer u sebi
  sadrži stvarnu okolinu te instalacije.

Za temperaturu dovodne vode se ne koristi tablica nego **flotni sezonski
množitelj**: agregirana potrošena energija kroz cijelu flotu, pripijena godišnja
sinusoida. Novi korisnik naslijedi flotnu krivulju i ima ispravnu korekciju od
prvog dana, bez godine povijesti. Ne pojavljuje se nijedan stupanj.

### 4.5 Klasifikacija negrijanih instalacija

Ispada besplatno iz sezonske varijacije `L`:

```
grijani stan:      L zima 53 W → ljeto 46 W    varijacija 17 %
negrijani prostor: L zima 69 W → ljeto 44 W    varijacija 57 %
```

Instalacije s velikom varijacijom su u negrijanom prostoru. Njima treba zaštita
od zamrzavanja: **nikad ih ne držati duboko nisko dugo zimi** — puknuti spremnik
je katastrofalan i vidljiv trošak.

---

## 5. Algoritmi

### 5.1 Procjena stanja — integrator

Stanje je manjak `d` u Wh ispod točke isklopa. Po koraku `Δt`:

```
ako grije:        d ← d − P·Δt
uvijek:           d ← d + L·Δt
nevidljiva potrošnja: d ← d + D          (nepoznato, samo se ograničava)
```

Prva dva člana su egzaktna: snagu mjeriš, `L` si kalibrirao. Treći je jedina
nepoznanica u sustavu i cijeli problem se svodi na to kako ga ograničiti.

Zato se vode **dvije granice**, ne jedan broj:

```
d_lo   pretpostavlja da potrošnje NIJE bilo     → najoptimističniji manjak
d_hi   pretpostavlja najgoru moguću potrošnju   → najpesimističniji manjak
```

`d_lo` je zagarantirani minimalni manjak, dakle **dokaziva apsorpcija**.
`d_hi` je zagarantirani maksimalni manjak, dakle ono protiv čega se čuva komfor.

### 5.2 Dva sidra i njihovi uvjeti valjanosti

**Sidro na isklopu.** Snaga padne s 2000 na 0 W dok je relej zatvoren.

```
d_lo = d_hi = 0
```

Egzaktno, besplatno, bez kalibracije. Ovo je glavno sidro. Fizički je pouzdano
jer grijanje na dnu diže toplu vodu uzgonom — kad sonda vidi zadanu temperaturu,
sve iznad nje je vruće.

**Sidro na uklopu.** Snaga skoči s 0 na 2000 W dok je relej zatvoren.

```
d_hi = min(d_hi, deficit_at_reclose_p95)
```

Samo **gornja** granica, i to je bitno. Uklop dokazuje da je sonda pala cijeli
histerezni pojas, ali sonda mjeri prosjek po svojoj visini. Nakon potrošnje
hladna voda ulazi na dno i sonda je odmah osjeti, iako je gore još vruća voda.
Dakle uklop nakon potrošnje **nije** dokaz da je spremnik na `E_capacity − E_hyst`
— on je uzrokovan hladnim dnom.

Uvjet valjanosti za bilo kakvo jače tumačenje uklopa: prije njega mora biti dug
period bez snage (≥4 h). Inače je uklop samo signal o dnu spremnika.

### 5.3 Nezdrava granica koja je izbačena

Izvorni dizajn je koristio zaključak:

> Relej zatvoren, struja ne teče → termostat isklopljen → voda je topla →
> **spremnik je skoro pun** → `d ≤ E_hyst`

Simulator je pokazao da je zadnji korak neistinit. **145 prekršaja u 45 dana,
najgori 1534 Wh** — jedan cijeli tuš. Mehanizam: sonda mjeri prosjek u donjoj
polovici, hladna voda ulazi na dno, vrh ostaje vruć, prosjek duž sonde može ostati
iznad točke uklopa iako je iz spremnika izašla znatna energija.

**Zdrava zamjena.** Dok je termostat otvoren, manjak može biti samo **manji** od
onoga koliki će biti u trenutku kad termostat uklopi. A taj se mjeri direktno —
to je energija dogrijavanja koje nakon uklopa slijedi. Dakle visoki percentil
opaženih energija dogrijavanja od uklopa do isklopa je valjana gornja granica
manjka:

```
dok je termostat otvoren:   d_hi ← min(d_hi, p95(energija uklop→isklop))
```

Za granicu treba **rep distribucije, ne medijan.** Medijan bi bio prosječni
slučaj, a granica mora pokrivati loš slučaj.

Ova formulacija ne tvrdi ništa o geometriji spremnika, i zato je valjana.

### 5.4 Kalibracija gubitka `L`

Najosjetljiviji parametar u sustavu, jer greška u njemu ide u **suprotnim
smjerovima** za dva proizvoda:

| Greška u `L` | Redukcija | Apsorpcija |
|---|---|---|
| previsok | misliš da gubiš brže → prekineš prerano → **sigurno** | misliš da ima više mjesta → obećaš previše → **kazna** |
| prenizak | misliš da imaš više vremena → **hladan tuš** | siguran, samo manje prodaš |

**Ne postoji smjer koji je konzervativan za oba.** Zato `L` mora biti točan, ne
konzervativan. To je jedini parametar u sustavu za koji to vrijedi.

**Formula koja je bila pogrešna:**

```
L = medijan(energija ciklusa) / NAJDULJA opažena pauza
```

Dijeljenje medijana jedne veličine s maksimumom druge — statistički nekoherentno.
Davala je **+21 % do +56 %** previsoko.

**Ispravna formula.** Iz jednog cijelog ciklusa termostata:

```
L_ciklus = E_ciklus / (pauza + trajanje grijanja)
```

Ključno svojstvo: ta procjena je **jednostrana**. Ako je bilo potrošnje,
dogrijavanje je duže i procjena je previsoka; ako nije bilo, procjena je točna.
**Nikad ne može biti preniska.** Zato:

```
L = p2 { L_ciklus  |  pauza ≥ 4 h }        kroz cijelu povijest
```

Kratki ciklusi su izbačeni jer su dominirani potrošnjom. Drugi percentil, a ne
minimum, radi robusnosti na šum mjerenja.

Izmjerena točnost protiv istine iz simulatora:

```
A03 samac 80 l       45,9 W  vs stvarni 46,1     −0,4 %
A07 par 80 l         45,0 W  vs stvarni 45,1     −0,2 %
A14 obitelj 4, 80 l  45,1 W  vs stvarni 42,5     +6 %
A01 samac 30 l       23,8 W  vs stvarni 23,8      0 %
```

**Pomični prozor ne radi.** Intuitivno bi 30-dnevni prozor pratio sezonu. Testiran
je i pogoršao je stvar na **+15 % do +54 %**, jer ciklusi bez potrošnje su rijetki
i grupiraju se u periodima odsutnosti, pa ih kratki prozor uglavnom ne sadrži.
Cijela povijest daje 0–6 %.

**`L` zahtijeva period odsutnosti korisnika.** S 200 dana podataka bez godišnjeg
odmora greška je **+25 % do +62 %**. Za neometani ciklus treba pauza od 15 sati
bez ijedne kapi tople vode, a domaćinstvo to napravi samo kad nikoga nema
(najdulja noćna pauza je 8 sati).

Zato kalibracija nosi zastavicu:

```
l_confident = broj ciklusa s pauzom ≥ 10 h  ≥  5
absorb_offerable = l_confident
```

**Uređaj ne smije nuditi apsorpciju dok nije viđen period odsutnosti.** Do tada je
`L` previsok, što je siguran smjer za redukciju i nesiguran za apsorpciju.

**Otvoreni defekt:** negrijane instalacije (11 % težine flote) podcjenjuju `L` za
**11–16 %**, jer ciklusi bez potrošnje dolaze iz ljetnog odmora kad negrijani
spremnik gubi najmanje. Podcjenjivanje je opasan smjer za redukciju. Rješenje koje
bi radilo: oblik sezonske krivulje je isti za sve negrijane instalacije u regiji,
pa ga se nauči jednom iz flote i primijeni. Nije napravljeno.

### 5.5 Kalibracija histereze `E_hyst`

```
E_hyst = p20 { E_ciklus  |  pauza ≥ 4 h,  uklop→isklop,  relej zatvoren }
```

Nizak percentil jer je i ta procjena jednostrana — potrošnja tijekom grijanja
može samo dodati energiju.

Provjera konzistentnosti kroz veličine spremnika: `E_hyst` po litri ispada
7,3–8,3 Wh/l za 30, 50, 80 i 120 litara, dakle histereza ≈ 6,4 K kroz sve modele.
To je ispravno, jer je širina histereze svojstvo bimetala a ne spremnika. Ta
provjera je u testovima.

### 5.6 Kalibracijska noć — mjerenje kapaciteta bez sudjelovanja korisnika

`E_capacity` se **ne može mjeriti pasivno**. Izmjereno na tri domaćinstva:

```
obitelj 4    5272 Wh   vs stvarni 4838    +9 %   ← precjenjivanje, opasno
par          2860 Wh   vs stvarni 4838   −41 %
samac        1900 Wh   vs stvarni 4838   −61 %
```

Podcjenjivanje jer se spremnik nikad ne isprazni do kraja. Precjenjivanje kod
obitelji jer potrošnja **tijekom** grijanja produži ciklus.

**Algoritam koji radi, i ne traži od korisnika ništa:**

```
1. Odaberi noć (npr. svakih 7 dana).
2. Od 17:00 drži relej OTVOREN.
   Korisnik svojim večernjim tuševima isprazni spremnik sam.
   Ti samo ne dopuštaš da se napuni.
3. Od 01:00 do 05:00 zatvori relej i grij neprekidno do isklopa.
4. Izmjeri integral snage. To je kapacitet.
```

Grijanje ide u 01–05 h jer je tada potrošnja najmanje vjerojatna, čime se izbjegava
napuhavanje mjerenja.

**Odgoda mora početi prije večernjih tuševa.** Ovo je bila greška u prvoj verziji:

```
odgoda od 21:00   →  izmjereno 717 Wh   (termostat je do 21 h već napunio spremnik)
odgoda od 19:00   →  izmjereno 1700 Wh
odgoda od 17:00   →  izmjereno 3283 Wh, najdublje noći dosegnu 4433 Wh
```

Teoretski maksimum je 4838 Wh, dakle odgoda od 17 h stvarno ispere spremnik.

**Statistika je maksimum, ne minimum.** Svaka noć daje **donju granicu** — dosegnuo
si onoliko duboko koliko je domaćinstvo tu noć slučajno potrošilo. Zato je najbolja
procjena visoki percentil ili maksimum. Prva verzija je uzimala p20 i podcjenjivala
četiri puta.

**Cijena kalibracije nije nula:**

```
par na 50 l (najtjesnji)    4 → 8 hladnih tuševa na 56 dana    +4
samac na 30 l              12 → 14                             +2
obitelj na 80 l            14 → 16                             +2
obitelj na 120 l            6 → 5                              −1 (unutar šuma)
```

Pravilo: **ne pokretati duboku kalibracijsku noć na bojlerima koji su i bez tebe
pretijesni.** Kriterij je odnos kapaciteta prema dnevnoj potrošnji.

**Zamka koju treba izbjeći:** prva verzija je prekidala odgodu kad bi `d_hi`
dosegnuo tekuću procjenu pojasa. Time je mjerenje bilo ograničeno vlastitom
početnom pretpostavkom i nikad nije raslo — kružna zavisnost. Odgoda ne smije biti
ograničena onim što mjeri.

### 5.7 Prodajni pojas

```
band = izmjereno dogrijavanje na kalibracijskoj noći
```

Nije `E_capacity` nego razlika `E_capacity − E_reserve`, jer se odgoda zaustavlja
prije nego naruši komfor. To je zgodno, jer je razlika **upravo ono što prodaješ** —
energija ispod rezerve komfora se nikad ne smije potrošiti, pa je nema smisla ni
mjeriti.

**Greška koju treba izbjeći:** `band = max(band, deficit_p95)`. Ta jedna linija je
napuhala pojas do najgoreg mogućeg manjka, kontroler je onda držao relej otvoren
88 % vremena, i 223 od 249 tuševa je palo. Pojas se **ne smije** vezati na granicu
manjka.

### 5.8 Izvođenje potrošnje i rezerva komfora

Potrošnja `D_k` se izvodi iz energetske bilance: nakon perioda bez grijanja,
energija dogrijavanja minus očekivani gubitak je potrošnja.

Ta izvedena serija, a **ne izmjerena snaga**, je ulaz u model navika. Ako se
agregira snaga, model uči vlastiti raspored optimizatora: pomakneš grijanje na
03 h, agregat pokaže grijanje u 03 h, i model zaključi da se korisnik tušira u
03 h. Povratna petlja koja se sama potvrđuje.

```
E_reserve(sat) = p90 { izvedena potrošnja u sljedeća 3 sata }   kroz 4–8 tjedana
```

Percentil, ne prosjek — za ograničenje rizika treba gornji rep. Prosjek daje
hladan tuš kad god se dogodi neuobičajen slučaj.

Fiksnih 20 % je zamijenjeno ovime jer je fiksni broj istovremeno pretijesan u
18:30 u obitelji i besmisleno širok u 03:00 u praznom stanu.

`E_shower` kao formula je **izbačen**. Formula
`V × 1,163 × (T_slavina − T_mreža)` traži volumen tuša i željenu temperaturu, a
oboje su nepoznanice. Umjesto toga: distribucija izmjerenih potrošnji tog
domaćinstva, grupirana po veličini (mala potrošnja < 200 Wh, tuš 800–1600 Wh,
kada > 2500 Wh). Medijan srednje skupine je „jedan tuš" **za tog korisnika**, bez
ijedne pretpostavke.

Za novu instalaciju: flotni prior, pa postupni prijelaz na vlastite podatke.

### 5.9 Interval observer — samo za komfor

```
odluka o redukciji:   d_hi + L·t + najgora_potrošnja(t)  ≤  band
```

Konzervativno, po uređaju, tvrda granica. Zato jer se greška ne može poolati:
hladan tuš u jednom stanu ne kompenzira topla voda u drugom.

**Extended Kalman Filter je odbačen.** Sustav je hibridan — kontinuirana energija,
diskretno skriveno stanje termostata, i nevidljivi diskretni događaji potrošnje s
raspodjelom koja je nula u većini intervala a dugorepa u ostalima. Sidra nisu
Gaussova mjerenja nego aktivacije nejednakosti. Gaussova linearizacija bi dala
pogrešnu procjenu vlastite pouzdanosti, a iz te pouzdanosti se izvode sigurnosne
margine.

### 5.10 Statistička ponuda na razini flote — za tržište

Ovo je odvojen alat od 5.9 i odgovara na drugo pitanje.

**Garancije nisu moguće.** Da granica bude zagarantirana, moraš pretpostaviti
najgoru moguću potrošnju u svakom trenutku. Testirano: budžet na p95 potrošnje po
satu daje **prekršaje u 27–97 % vremena**, jer napunjena kada je daleko iznad p95
bilo kojeg sata. A pravi najgori slučaj pojede cijeli pojas i ne prodaješ ništa.

Tržište ionako radi vjerojatnosno:

```
ponuda maksimizira:  prihod od kapaciteta + aktivacije − očekivana kazna
```

**Razdvajanje varijance.** Vrijeme tuširanja je nezavisno između domaćinstava, pa
se poništava s korijenom iz N. Sezona, praznici, kolektivni godišnji, ispad
interneta — to pomiče cijelu flotu i **ne poništava se**.

```
ponuda = prosjek(sat, sezona, tip dana) − margina samo za KORELIRANU varijancu
```

Izmjereno na sintetskoj floti (arhetip odabran po težini, plus dan-offset po
uređaju radi dekoreliranja):

```
uređaja    p1 / prosjek
   100        0,47
   500        0,66
 1.000        0,71
 5.000        0,76
20.000        0,78
```

Do tisuću uređaja se ponuda dramatično stabilizira, nakon toga **stane na
76–78 %.** Preostalih 22–24 % je korelirana komponenta i strukturna je.

**Greška koju treba izbjeći:** sabiranje p10 svakog uređaja posebno kao da svih
5000 pogodi dno u istoj sekundi. To je davalo flotni p10 od nule, što je besmisleno.
Flotni percentil se računa na **zbiru**, ne kao zbir percentila.

### 5.11 Probni impulsi — mali uzorak, ne mehanizam

Zatvaranje releja 2–3 sekunde tijekom redukcije, radi očitanja stanja termostata.
Cijena 1,7 Wh.

```
teče 2000 W   →  termostat zatvoren  →  spremnik ima mjesta
teče 0 W      →  termostat otvoren   →  spremnik je pun
```

**Za redukciju je gotovo bezvrijedan.** Testira jedan jedini prag na 85 %
kapaciteta. Kad ga prijeđeš, svaki daljnji impuls pokazuje 2000 W i ne kaže ništa
novo. A prag prijeđeš u prvom satu duboke redukcije.

**Za apsorpciju je vrjedniji, ali ne kao dokaz po uređaju.** Statistika nosi
glavninu procjene. Impuls uklanja samo **koreliranu** komponentu — današnje
stvarno stanje flote, koje statistika ne može pokratiti.

A za to ne treba impulsirati flotu nego **anketirati uzorak**:

```
200 uređaja od 5000  →  točnost udjela spremnih 3,5 %
```

Svaki uređaj dođe na red jednom u 25 intervala, čime propada zabrinutost o
trošenju kontakata.

**I dobar dio se dobije besplatno:** uređaji koji trenutno nisu u aktivaciji imaju
relej zatvoren, pa im se stanje termostata vidi stalno, bez ijednog impulsa. Iz
njih se očita današnji radni ciklus flote. Impuls onda fiksira samo pomak zbog
odgode.

### 5.12 Detekcija promjene termostata

Sva sidra su vezana na termostat, pa se pri promjeni kotačića **pomaknu zajedno s
njim** i promjena je iz sidara nevidljiva. Jedini fizički signal vezan na
apsolutnu temperaturu je `L`, jer gleda prema prostoriji, i `E_capacity`, jer se
mjeri od temperature mreže.

Potpis promjene kotačića +10 K:

```
E_capacity   +19 %    vidiš za dane do tjedan
L            +25 %    vidiš za tjedne
E_hyst       ništa
E_reserve    ništa
```

Nijedan drugi uzrok ne daje tu kombinaciju. Razlikovanje od kapajuće tople vode:
kapanje diže **samo** `L`, kotačić diže i `L` i `E_capacity` zajedno.

**Najbrži signal nije mjerni nego ponašajni:** gomilanje Boost pritisaka, dostupno
u satima. Nezadovoljan korisnik prvo stisne Boost nekoliko puta, pa onda ustane i
zavrne kotačić.

Reakcija: odmah u konzervativni režim bez čekanja potvrde, jer je **spuštanje**
kotačića opasan smjer i prvi simptom je hladan tuš. Zatim odredi smjer, pa te noći
ponovno izmjeri kapacitet.

### 5.13 Dispečiranje i zaštita mreže

**Jitter rješava samo elektrotehnički korak.** Raspoređivanje uklopa kroz 60
sekundi pretvara skok struje na izvodu u rampu — to je vremenska skala sekundi.
Termičko opterećenje trafostanice je vremenska skala minuta do sati, i tu je 60
sekundi zaokruživanje. Energija oporavka je fiksna: svaki odgođeni kWh se mora
potrošiti.

**Oporavak se raspoređuje kroz desetke minuta**, u valovima, prioritetno po
preostaloj energiji. Ideja State Queueing je ispravna, vremenska skala u izvornom
planu je pogrešna za dva reda veličine.

**Veličina povratnog vrha je precijenjena u izvornom planu.** „50.000 × 2 kW =
100 MW" pretpostavlja da svi upale. Pri radnom ciklusu od 17 % nakon jednosatne
redukcije realno 20–40 % je spremno, dakle 20–40 MW. Skalira s veličinom flote —
pri 5000 uređaja je 2–4 MW.

**Geografsko grupiranje.** Dvadeset bojlera na jednoj trafostanici je veći lokalni
problem od 50.000 raspoređenih po zemlji. Nisku mrežu ne poznaješ, pa se koristi
poštanski broj kao zamjena i randomizira **unutar** grupe, da nijedan izvod ne
dobije koordiniranu naredbu.

**PEM je arhitekturno nekonzistentan** s ovim dizajnom: traži da procjena stanja
živi na uređaju, a uređaj je relej bez termometra. Serverska randomizirana kontrola
pristupa je matematički ekvivalentna i mnogo jednostavnija.

**Governor u Erlangu, ne u Pythonu.** Tvrdo ograničenje na agregatnu promjenu
stanja po minuti, na zadnjem skoku prije izlaska naredbe, koje odbija bilo koji
dispeč iznad granice bez obzira što je optimizator zatražio. To je kontrola koja
preživi kompromitiran ili pogrešan mozak sustava.

### 5.14 Što je odbačeno i zašto

| Odbačeno | Razlog |
|---|---|
| Extended Kalman Filter | sustav je hibridan, sidra nisu Gaussova mjerenja |
| PINN | nepoznanice su 3–5 skalara koje aritmetika daje s nesigurnošću i interpretacijom |
| Fokker–Planck populacijska kontrola | nepotrebno ispod ~10.000 uređaja |
| PEM na uređaju | uređaj nema procjenu stanja; serverska verzija je ekvivalentna |
| GEKKO | problem je MILP a ne MINLP; `remote=True` šalje model na javni server |
| SciPy fit krivulje hlađenja | nema što fitati, temperatura se ne mjeri |
| `E_shower` formula | traži volumen tuša i željenu temperaturu, oboje nepoznato |
| donja granica iz uklopa | u trenutku kad naučiš da ima mjesta, bojler ga već sam puni |
| fiksna rezerva od 20 % | istovremeno pretijesna i preširoka, ovisno o satu |
| prognoza vremena za `L` | `L` je direktno mjerljiv; prognoza bi dala lažni osjećaj znanja |
| tablica temperature mreže | flotni sezonski množitelj je mjeren i radi od prvog dana |

---

## 6. Simulator

### 6.1 Zašto postoji

U stvarnosti se temperatura vode nikad ne zna, pa se procjena algoritma nikad ne
može provjeriti — nema s čime usporediti. U simulatoru je temperatura broj koji se
može pročitati kad god se želi, a algoritam dobiva **isključivo ono što bi Shelly
dao u stvarnom stanu**: stanje releja i vate. Razlika između njegove procjene i
istine je greška.

Bez toga se ne može odgovoriti ni na jedno pitanje o pojasu nesigurnosti, a od
njega ovisi cijeli poslovni model.

### 6.2 Struktura

```
apps/simulator/
├── aquacell_sim/
│   ├── tank.py               slojeviti model spremnika + mehanički termostat
│   ├── draws.py              generator potrošnje, profili domaćinstva
│   ├── calendar_hr.py        hrvatski praznici, sezonske krivulje, tipovi dana
│   ├── scenarios.py          10 scenarija za brze testove
│   ├── archetypes.py         20 arhetipova s populacijskim težinama
│   ├── estimator.py          kalibrator + interval observer (ono što se testira)
│   ├── experiment.py         harness, politike upravljanja, detekcija hladnog tuša
│   ├── year.py               godišnja simulacija s kalendarom i zapisom
│   ├── run_year.py           generira dataset (23 min za 20 arhetipova)
│   ├── analyse_year.py       flotni agregat po satu i mjesecu
│   ├── analyse_windows.py    kapacitet po tržišnim prozorima
│   ├── analyse_fleet.py      sintetska flota, percentili zbira
│   ├── analyse_statistical.py  dokazivo vs statistički
│   └── run_risk_sweep.py     sweep po razinama rizika
├── tests/
│   ├── test_tank.py          6 testova fizike
│   └── test_calibration.py   5 testova točnosti kalibracije
└── data/
    ├── year_15min.csv.gz     16 MB, 20 arhetipova, red po 15 min
    ├── year_events.csv.gz    622 kB, svaki isklop i uklop
    ├── year_summary.csv      jedan red po arhetipu
    └── metadata.json         definicije, težine, shema, ograđivanje
```

Pokretanje:

```bash
python3 -m pytest -m "not slow"          # 21 s
python3 -m pytest -m slow                # 7 min, puna godina
python3 -m aquacell_sim.run_year          # 23 min, generira dataset
python3 -m aquacell_sim.analyse_fleet 5000
```

### 6.3 Fizika spremnika

Spremnik je podijeljen na **12 vodoravnih slojeva**, svaki s vlastitom
temperaturom. Po koraku, u ovom redu:

1. **Grijač** dodaje toplinu svom sloju (sloj 1, blizu dna).
2. **Potrošnja** potiskuje vodu prema gore (upwind advekcija): hladna ulazi na dno,
   topla izlazi s vrha. Sub-korak ako povučeni volumen prelazi pola sloja.
3. **Gubitak** po sloju prema okolini, `UA/N × (T_i − T_amb)`.
4. **Vođenje** topline između susjednih slojeva.
5. **Uzgon**: svaka inverzija (donji sloj topliji od gornjeg) se izmiješa, ponavlja
   se do stabilnosti.

Peti korak daje najvažnije ponašanje: grijač na dnu grije svoj sloj, ta voda
postane lakša i digne se, pa se **vrh grije prvi** a dno ostaje hladno. Zato voda
ispod grijača nikad ne dođe do zadane temperature osim vođenjem — to je stvarni
mrtvi volumen na dnu vertikalnog bojlera.

`_mix_inversions` je pisan kao skalarna petlja, ne numpy: za polje od 12 elemenata
je numpy overhead red veličine veći od same aritmetike, a ovo se izvršava u svakom
koraku svake simulirane godine.

### 6.4 Mehanički termostat

```
zatvoren dok sonda < zadana temperatura
otvara se kad sonda dosegne zadanu
ostaje otvoren dok sonda ne padne cijeli histerezni pojas
```

**Sonda mjeri prosjek kroz vertikalni raspon**, ne u točki. Stvarni termostat u
prirubnici grijača je šipka koja seže u spremnik.

Ovo je **jedini podešeni parametar u fizici** i to treba znati:

```
raspon 1 sloj    →  E_hyst 519 Wh
raspon 3 sloja   →  E_hyst 618 Wh
raspon 6 slojeva →  E_hyst 683 Wh    ← odabrano
raspon 11 slojeva→  E_hyst 717 Wh
```

Odabran je raspon 6 jer reproducira ručno izračunatih 744 Wh. **To je kružno** —
model se slaže s očekivanjem, ali to ne dokazuje da se slaže sa stvarnim bojlerom.
Provjerava se u jednoj noći na pravom uređaju: pusti ga da miruje i izmjeri
trajanje grijanja. Ako je 22 minute, model je dobar; ako je 8 minuta, sonda je
drugačije postavljena.

### 6.5 Generiranje potrošnje

Nije unaprijed zapisan raspored nego **stohastički proces po danu**:

```
broj tuševa toga dana  ~  Poisson(članovi × tuševa po osobi)
sat svakog tuša        ~  iz 24 težine ovisnih o TIPU DANA
minuta unutar sata     ~  uniformno
volumen tuša           ~  Normal(nominalni, 20 %) × sezonski faktor
temperatura slavine    ~  Normal(40 °C, 1 K)
male potrošnje         ~  Poisson(dnevna stopa), volumen ~ Exponential
kada                   ~  Bernoulli(dnevna vjerojatnost)
gosti                  ~  Bernoulli(2 %) → +1 do 2 osobe tog dana
```

Težine po satu se razlikuju po tipu dana:

| tip dana | jutarnji vrh | napomena |
|---|---|---|
| radni | oštar, 06–08 | najviša težina u 07 h |
| rad od doma | blaži, 06–09 | plus dodatne male potrošnje kroz dan |
| subota | pomaknut, 08–11 | više kada |
| nedjelja / praznik | još kasnije, 09–11 | |
| odsutni | **ništa** | godišnji odmor, prazna vikendica |

### 6.6 Kalendar

Hrvatski praznici, uključujući Uskrs i Tijelovo izračunate iz datuma Uskrsa
(anonimni gregorijanski algoritam). Školski praznici približno. Godišnji odmor
2–3 tjedna u srpnju ili kolovozu, slučajno postavljen. Zimski prekid za dio
arhetipova.

Sezonske krivulje, sve kao glatke sinusoide:

```
temperatura mreže     13 − 5·cos(2π(dan−52)/365)      → 8 °C kraj veljače, 18 °C kraj kolovoza
vanjski zrak          12,5 − 11·cos(2π(dan−15)/365)   → 1,5 °C sredina siječnja, 23,5 °C srpanj
okolina grijano       21 + 0,35·max(0, vanjska−12)    → 21 zima, 25 ljeto
okolina negrijano     0,75·vanjska + 0,25·15          → 5 zima, 21 ljeto
tuš sezonski faktor   1 + 0,08·cos(...)               → zimi 8 % dulji tuš
```

### 6.7 Dvadeset arhetipova

Nisu uzorak nego **namjerna mreža** koja pokriva prostor: veličina spremnika ×
broj članova × intenzitet × grijano/negrijano × režim rada. Svaki nosi
populacijsku težinu, i flota bilo koje veličine se generira uzorkovanjem po tim
težinama.

```
A01  samac, 30 l, garsonjera                    0,05
A02  samac, 50 l                                0,06
A03  samac, 80 l, predimenzionirano             0,06
A04  samac, 50 l, negrijana kupaonica           0,02
A05  samac, 80 l, rad od doma 3 dana            0,03
A06  par, 50 l, poddimenzionirano               0,05
A07  par, 80 l, tipično                         0,09
A08  par, 80 l, oba rade od doma                0,04
A09  par, 100 l                                 0,04
A10  par, 80 l, bojler u podrumu                0,03
A11  obitelj 3, 80 l                            0,08
A12  obitelj 3, 100 l                           0,05
A13  obitelj 3, 80 l, jedan roditelj od doma    0,03
A14  obitelj 4, 80 l, poddimenzionirano         0,07
A15  obitelj 4, 120 l, ispravno                 0,07
A16  obitelj 4, 100 l, negrijana kupaonica      0,03
A17  obitelj 5, 120 l                           0,05
A18  obitelj 5, 150 l, 3 kW                     0,02
A19  vikendica, 80 l, samo vikendom             0,03
A20  najam / studenti, 80 l, dugi tuševi        0,10
```

**Težine su procjena, ne podatak.** Skupljene su na jednom mjestu upravo zato da
se mogu zamijeniti bez traženja po kodu. Njihova zamjena mijenja svaku flotnu
brojku; ništa drugo u simulatoru ne ovisi o njima.

Gubitak se skalira s površinom, `UA ∝ V^(2/3)`: 26 W za 30 l, 50 W za 80 l, 95 W
za 120 l.

A18 s grijačem od 3 kW **prekoračuje granicu prekapčanja Shelly 1PM Gen3 od
2000 W** i označen je zastavicom `needs_contactor`.

### 6.8 Kako se mjeri hladan tuš

Ne pretpostavlja se iz praga energije nego se **mjeri na slavini**.

Korisnik želi 40 litara od 40 °C. Mješalica miješa vruću iz spremnika s hladnom
iz cijevi:

```
ako je vrh spremnika > željene:  udio vruće = (T_želj − T_mreža)/(T_vrh − T_mreža)
ako je vrh spremnika ≤ željene:  sva voda iz spremnika, dostavljeno = T_vrh
```

Za svaki događaj se prati koliko je litara isteklo iznad `željena − 2 K`. Ako je
manje od 90 % volumena bilo prihvatljivo, **tuš je pao**.

Korisnik nikad ne dobije mlaku vodu od 25 °C — dobije **manju količinu ispravno
vruće vode**, pa onda naglo hladnu. To je bitna razlika i dugo je bila pogrešno
opisana u ranijim analizama.

### 6.9 Validacija fizike

Ručni izračun je napravljen **prije** koda, iz prvih principa:

| veličina | ručno | simulator (Δt=30 s) | simulator (Δt=60 s) |
|---|---|---|---|
| `E_hyst` | 744 Wh | 683 Wh | 700 Wh |
| prazna pauza | 14,9 h | 13,55 h | 13,84 h |
| gubitak `L` | 50,0 W | 49,2 W | 49,3 W |

Šest testova u `test_tank.py` čuva: očuvanje energije bez gubitka i potrošnje,
dizanje topline prema vrhu, ulazak hladne vode na dno, gubitak proporcionalan
`UA`, reprodukciju vremenskih skala praznog ciklusa, i histerezu termostata.

Pet testova u `test_calibration.py` čuva točnost `L` (±12 % za grijane), dokumentira
poznatu pristranost za negrijane (−35 % do +10 %, označeno kao otvoreni defekt),
konzistentnost `E_hyst` po litri kroz veličine spremnika, i **uvjet da se apsorpcija
ne nudi dok `L` nije pouzdan**.

### 6.10 Performansa

Vremenski korak 60 s, godina po arhetipu je 525.600 koraka, ~75 s po arhetipu,
23 minute za svih 20.

Dvije optimizacije su bile nužne:

**Gusti raspored potrošnje.** Prva verzija je u svakom koraku linearno pretraživala
listu događaja — za godinu i ~3000 događaja to je oko milijardu usporedbi i
dominiralo je cijelom simulacijom. Predračun po koraku traje nekoliko megabajta.

**Skalarno miješanje** umjesto numpy, kako je opisano u 6.3.

### 6.11 Što je utemeljeno, što podešeno, što izmišljeno

Ovo je najvažnije poglavlje za procjenu vjerodostojnosti rezultata.

**Utemeljeno.** Termodinamika spremnika. Gubitak postavljen tako da daje
1,2 kWh/dan, što je energetska klasa C s naljepnice koju svaki bojler ima.
Neovisna provjera prema ručnom izračunu iz 6.9.

**Podešeno.** Vertikalni raspon sonde termostata (6.4). Podešen je da reproducira
očekivano trajanje grijanja, dakle **kružno**, i to je jedina stvar iz simulatora
koju treba provjeriti na pravom bojleru.

**Izmišljeno, ali razumno.** Sve o ponašanju ljudi: 40 litara po tušu, jedan tuš
dnevno po osobi, oblik krivulje po satima, kada jednom u četiri dana, 20 malih
potrošnji dnevno, težine arhetipova. Iz općeg znanja o dimenzioniranju sanitarne
vode i konvencija europskih norma za testiranje bojlera. **Nije izmjereno na
nijednom hrvatskom domaćinstvu.**

**Vjerojatno pogrešno u poznatom smjeru:** potrošnja mi je 15–25 % previsoka. A07
daje 2429 kWh/god za par, a tipične hrvatske vrijednosti su 1500–2500. Male
potrošnje računam kao punu toplu vodu, što je pretjerano.

Posljedica za povjerenje:

**Zaključcima o mehanizmima se može vjerovati** — da je „termostat otvoren znači
spremnik pun" pogrešno slijedi iz slojevitosti i vrijedi za bilo koji profil
potrošnje. Isto za nužnost odgode prije večernjih tuševa, za nemogućnost
garancije, i za suprotne zahtjeve na točnost `L`.

**Apsolutnim brojkama se ne može vjerovati.** Nose neizvjesnost od otprilike
faktora 1,5.

**Rangiranje arhetipova je robusno**, jer ga vodi odnos kapaciteta prema dnevnoj
potrošnji, a to je aritmetika koja ne ovisi o tome je li tuš 40 ili 32 litre.

### 6.12 Kako se izmišljeni dio zamjenjuje pravim

Sustav **već izvodi potrošnju iz energetske bilance** (5.8). To je upravo podatak
koji simulatoru treba. Prva instalacija kroz nekoliko tjedana proizvede stvarnu
distribuciju potrošnji za jedno stvarno domaćinstvo; s deset instalacija profili
postaju upotrebljivi.

Redoslijed nije „prvo simulator pa hardver" nego: simulator sada za testiranje
mehanizama, jedan Shelly za provjeru sonde i prvu stvarnu distribuciju, pa
simulator ponovno s izmjerenim profilima.

---

## 7. Rezultati

Flota 5000 uređaja, nazivno 10.215 kW (težinski prosjek 2043 W po uređaju).

### 7.1 Po satu dana

Prva tri stupca su po jednom uređaju, zadnja dva cijela flota.

| sat | baza W/ured | dolje W/ured | gore W/ured | dolje MW | gore MW |
|---|---|---|---|---|---|
| 00 | 60 | 50 | 801 | 0,25 | 4,00 |
| 01 | 309 | 48 | 667 | 0,24 | 3,34 |
| 02 | 192 | 53 | 777 | 0,26 | 3,88 |
| 03 | 74 | 47 | 890 | **0,23** | 4,45 |
| 04 | 66 | 55 | 968 | 0,28 | **4,84** |
| 05 | 199 | 177 | 901 | 0,89 | 4,50 |
| 06 | 496 | 396 | 605 | 1,98 | 3,02 |
| **07** | 679 | 408 | 379 | **2,04** | 1,90 |
| 08 | 607 | 355 | 303 | 1,78 | **1,51** |
| 09 | 458 | 297 | 321 | 1,49 | 1,61 |
| 10 | 382 | 274 | 373 | 1,37 | 1,86 |
| 11 | 360 | 269 | 419 | 1,34 | 2,10 |
| 12 | 392 | 288 | 414 | 1,44 | 2,07 |
| 13 | 341 | 258 | 403 | 1,29 | 2,02 |
| 14 | 268 | 213 | 440 | 1,07 | 2,20 |
| 15 | 290 | 223 | 461 | 1,12 | 2,30 |
| 16 | 378 | 276 | 422 | 1,38 | 2,11 |
| 17 | 476 | 312 | 355 | 1,56 | 1,78 |
| 18 | 611 | 366 | 311 | 1,83 | 1,56 |
| 19 | 634 | 359 | 323 | 1,79 | 1,61 |
| 20 | 555 | 341 | 366 | 1,70 | 1,83 |
| 21 | 399 | 293 | 435 | 1,46 | 2,18 |
| 22 | 233 | 194 | 534 | 0,97 | 2,67 |
| 23 | 108 | 95 | 662 | 0,47 | 3,31 |

**Kako čitati `baza`.** Bojler je isključen (0 W) ili grije (2000 W), nikad 610 W.
Prosjek od 610 W u 8 h znači da **oko 30 % bojlera grije** u tom trenutku.

**`dolje` nikad ne može biti veće od `baza`** — ne može se skinuti snaga koja ne
teče. To je fizika, ne pretpostavka. Uz to je ograničeno pojasom energije: u 70 %
blokova gdje bojler ne radi dobiješ nulu, u 30 % gdje radi ograniči te pojas, i
prosjek te mješavine je 355 W.

**`gore` je ograničeno s `nazivno − baza`** i količinom mjesta u spremniku.

**Oblik je obrnut** jer redukcija zahtijeva da nešto radi, a apsorpcija da nešto ne
radi. Suprotni uvjeti, suprotni najbolji sati.

Prosjek kroz dan: **redukcija 1.176 kW (11,5 % nazivne), apsorpcija 2.610 kW
(25,6 %)**. Raspon redukcije kroz dan je faktor devet.

### 7.2 Po mjesecu, W po uređaju

```
        sij   velj   ozu   tra   svi   lip   srp   kol   ruj   lis   stu   pro
dolje     0    174   331   317   285   238   145   169   186   211   246   273
gore      0    518   528   535   544   572   811   602   436   403   388   399
```

Siječanj je nula jer je to prvih 30 dana skupljanja podataka bez upravljanja — to
je dizajn, ne rezultat.

Redukcija je najjača u ožujku, najslabija u srpnju (godišnji odmori, nema što
reducirati). Apsorpcija obrnuto, vrh u srpnju.

**Nezgodno:** redukcija je najvrjednija zimi a slabija u ljetnim mjesecima, ali
najgori mjesec je ipak srpanj kad je i cijena niska — poklapanje je u našu korist.

### 7.3 Tržišni prozori, sintetska flota

Prozori su definirani po tome kad mreža stvarno traži svaki smjer.

| prozor | smjer | prosjek | p10 | **p1** | po uređaju (p1) |
|---|---|---|---|---|---|
| jutarnji vrh 06–09 | redukcija | 1,80 MW | 1,44 | **1,38 MW** | 276 W |
| večernji vrh 17–21 | redukcija | 1,67 MW | 1,35 | **1,24 MW** | 248 W |
| solarni višak 10–16 | apsorpcija | 2,09 MW | 1,92 | **1,74 MW** | 348 W |
| noćni višak 00–05 | apsorpcija | 4,17 MW | 3,43 | **3,08 MW** | 616 W |

`p1` je vrijednost koju prekoračiš u 99 % petnaestminutnih blokova — brojka koja
smije u ponudu.

Uređaja za 1 MW u tom prozoru, prema `p1`:

```
noćni višak, apsorpcija     ~1.600
solarni višak, apsorpcija   ~2.900
jutarnji vrh, redukcija     ~3.600
večernji vrh, redukcija     ~4.000
```

### 7.4 Skaliranje flote — najvažnija tablica u dokumentu

```
uređaja    p1 / prosjek (jutarnja redukcija)
   100                 0,47
   500                 0,66
 1.000                 0,71
 5.000                 0,76
20.000                 0,78
```

Do tisuću uređaja se ponuda dramatično stabilizira. Nakon toga **stane na 76–78 %
i dalje ne raste.**

**Veća flota kupuje količinu, ne pouzdanost.** Iznad tisuću uređaja je haircut od
22–24 % strukturan i ostaje zauvijek. To je korelirana komponenta: svi bojleri
dijele isti sat u danu, isti dan u tjednu, iste praznike.

### 7.5 Po arhetipu, godišnji prosjek

| id | težina | baza W | dolje W | gore W | pojas Wh | širina Wh | kWh/god | pali tuševi |
|---|---|---|---|---|---|---|---|---|
| A01 | 0,05 | 144 | 99 | 256 | 236 | 707 | 1144 | 10,8 % |
| A02 | 0,06 | 168 | 118 | 422 | 346 | 912 | 1329 | 7,2 % |
| A03 | 0,06 | 197 | 125 | 635 | 362 | 1016 | 1558 | 3,9 % |
| A04 | 0,02 | 177 | 126 | 450 | 377 | 901 | 1400 | 5,9 % |
| A05 | 0,03 | 227 | 153 | 569 | 545 | 1098 | 1796 | 4,0 % |
| A06 | 0,05 | 270 | 178 | 357 | 341 | 1105 | 2138 | 13,2 % |
| A07 | 0,09 | 302 | 188 | 526 | 627 | 1466 | 2394 | 4,3 % |
| A08 | 0,04 | 357 | 238 | 453 | 833 | 1621 | 2829 | 5,2 % |
| A09 | 0,04 | 313 | 193 | 636 | 913 | 1654 | 2477 | 2,5 % |
| A10 | 0,03 | 308 | 187 | 568 | 814 | 1625 | 2436 | 6,0 % |
| A11 | 0,08 | 401 | 253 | 461 | 945 | 1971 | 3175 | 9,8 % |
| A12 | 0,05 | 420 | 283 | 581 | 1548 | 2140 | 3329 | 5,5 % |
| A13 | 0,03 | 454 | 305 | 427 | 1179 | 1944 | 3597 | 8,5 % |
| A14 | 0,07 | 507 | 340 | 436 | 1438 | 2296 | 4012 | 13,8 % |
| A15 | 0,07 | 527 | **388** | 634 | 2409 | 2848 | 4172 | 3,9 % |
| A16 | 0,03 | 520 | 312 | 546 | 1223 | 2715 | 4121 | 6,9 % |
| A17 | 0,05 | 629 | **398** | 588 | 2041 | 3149 | 4985 | 6,2 % |
| A18 | 0,02 | 644 | **429** | 775 | 1608 | 3012 | 5101 | 1,4 % |
| A19 | 0,03 | 183 | 109 | **854** | 157 | 1560 | 1448 | 7,6 % |
| A20 | 0,10 | 363 | 243 | 533 | 1000 | 1790 | 2877 | 8,4 % |

**Fleksibilnost dolazi iz potrošnje, ne iz spremnika.** To je suprotno intuiciji.
Samac s 80 litara (A03) ima kapacitet 4838 Wh ali kalibracija dosegne samo 15 % —
nikad ga ne isprazni, pa mu ostatak ne može ni izmjeriti, a kamoli prodati.
Obitelj s istim spremnikom (A14) dosegne 68 %.

**Korisnike treba birati po potrošnji, ne po veličini bojlera.** Screening je
trivijalan: iz prvih tjedana telemetrije se vidi dnevna energija.

**Vikendica (A19) je najbolji apsorpcijski resurs u floti** — 854 W. Prazna je pet
dana u tjednu, spremnik uvijek ima mjesta, i nikoga ne možeš naljutiti jer nikoga
nema. Ako je apsorpcija glavni proizvod, prazni i vikend-stanovi su vrjedniji nego
što bi se pomislilo.

**Širina pojasa nesigurnosti (642–3149 Wh) je red veličine veća od prodajnog
pojasa.** To je odgovor na pitanje s kojim je cijela analiza počela, i objašnjava
zašto je redukcija slab proizvod. Apsorpcija na to reagira slabije, jer punjenje
spremnika nikoga ne može ostaviti bez tople vode.

### 7.6 Hladni tuševi bez ikakve kontrole

Bazna razina **nije nula**:

```
A14 obitelj 4 na 80 l     13,8 %  ← poddimenzionirano
A06 par na 50 l           13,2 %  ← poddimenzionirano
A01 samac na 30 l         10,8 %
A15 obitelj 4 na 120 l     3,9 %  ← ispravno dimenzionirano
A18 obitelj 5 na 150 l     1,4 %
```

Peti tuš u nizu je hladan i bez tebe. Dvije posljedice: kad korisnik pozove, to ne
znači da si ti kriv; i treba mjeriti **koliko si hladnih tuševa dodao**, a ne
koliko ih ukupno ima. To je i argument u razgovoru s korisnikom.

Bojler od 30 litara drži 1814 Wh a jedan tuš košta 1489 Wh — **cijeli spremnik je
1,2 tuša.** Tu nema pojasa i nema proizvoda, i to se ne može popraviti algoritmom.

### 7.7 Pošteno, u megavatima

Odstupanja koja još nisu u simulaciji:

| što | smjer | veličina |
|---|---|---|
| potrošnja mi je previsoka | redukcija precijenjena | −20 % |
| korelirani ispadi konektivnosti nisu modelirani | oba | −8 % |
| novi uređaj ne smije nuditi apsorpciju do prvog odmora | apsorpcija, flota koja raste | −25 % |
| negrijane instalacije, `L` podcijenjen | redukcija precijenjena | −2 % |
| težine arhetipova su procjena | oba | ±20 % |

```
noćna apsorpcija     00–05     1,7 – 2,8 MW      (zrela flota 2,8)
solarna apsorpcija   10–16     1,0 – 1,6 MW      (zrela flota 1,6)
jutarnja redukcija   06–09     0,8 – 1,2 MW      (procjena 1,0)
večernja redukcija   17–21     0,7 – 1,1 MW      (procjena 0,9)
```

Minimalna ponuda za standardni proizvod je 1 MW.

**Noćna apsorpcija:** 5000 uređaja daje 2 MW pošteno, dakle 1 MW s udvostručenom
marginom. Za 1 MW treba **oko 2.400 uređaja.**

**Jutarnja redukcija:** 5000 uređaja daje 1,0 MW — **točno na pragu, bez margine.**
Za 1 MW s marginom treba 7.000–8.000.

**Večernja redukcija:** 5000 uređaja ne dostiže 1 MW pouzdano.

Jednom rečenicom: **od 5000 bojlera možeš pošteno prodati oko 2 MW noćne
apsorpcije ili oko 1 MW jutarnje redukcije, ali ne oboje.**

---

## 8. Dnevnik ispravaka

Ovo je najkorisnije poglavlje za buduću implementaciju. Svaka od ovih grešaka je
bila napravljena i ispravljena, i svaka se lako napravi ponovno.

### 8.1 Greške u izvornom dizajnu

**1. Jednadžba stanja je bila dimenzijski pogrešna.** `α·SoC` pretpostavlja da je
gubitak proporcionalan razlici prema granici komfora, a fizički je prema
prostoriji. Ispravak: raditi u energiji.

**2. `E_hyst` je pogrešan detektor promjene termostata.** Širina histereze je
svojstvo bimetala i ne mijenja se kad korisnik zavrne kotačić. Ispravni detektori
su `L` i `E_capacity`, plus Boost pritisci kao vodeći signal.

**3. `L` se ne može mjeriti svaku noć.** Prazna pauza je 15 sati; domaćinstvo je
nikad ne napravi osim kad nikoga nema. Prva procjena da je to noćni test od
01–05 h bila je pogrešna za faktor tri.

**4. Sva sidra su vezana na termostat, pa je promjena kotačića iz njih nevidljiva.**
Isklop je „setpoint", uklop je „setpoint minus histereza"; ako se setpoint digne,
oba se dignu i razlika ostane ista.

**5. Zaključak „termostat otvoren znači spremnik pun" je neistinit.** 145 prekršaja
u 45 dana, najgori 1534 Wh. Uzrok je slojevitost i to što sonda mjeri prosjek u
donjoj polovici spremnika.

**6. `E_capacity` se ne može mjeriti pasivno.** −61 % do +9 %, i precjenjivanje je
opasan smjer. Treba forsirana kalibracijska noć.

**7. Garancije nisu moguće.** Budžet potrošnje na p95 po satu daje prekršaje u
27–97 % vremena, jer kada probija svaki kvantil. Pravi najgori slučaj pojede cijeli
pojas.

**8. Jednočvorni pesimizam nije bezuvjetno siguran.** Za komfor je siguran, ali
košta prihoda: govorio je da oporavak traje 89 minuta prije prve tople vode, a
stvarnost je desetak minuta, jer se u slojevitom spremniku vrh zagrije prvi.

**9. `L` mora biti točan, ne konzervativan.** Ne postoji smjer greške koji je
siguran za oba proizvoda. To je jedini takav parametar u sustavu.

**10. `L` zahtijeva period odsutnosti korisnika**, pa apsorpcija mora biti
uvjetovana zastavicom pouzdanosti. Novi uređaj mjesecima ne može prodavati
apsorpciju — to ulazi u izračun povrata na trošak ugradnje.

### 8.2 Greške u mojoj implementaciji simulatora

**11. `band = max(band, deficit_p95)`.** Jedna linija koja je napuhala prodajni
pojas do najgoreg mogućeg manjka. Kontroler je držao relej otvoren 88 % vremena i
223 od 249 tuševa je palo.

**12. Kružna zavisnost u kalibracijskoj noći.** Odgoda je prekidala kad bi `d_hi`
dosegnuo tekuću procjenu pojasa, pa je mjerenje bilo zaključano na vlastitoj
početnoj pretpostavci i nikad nije raslo.

**13. Pogrešan smjer percentila.** Za pojas iz kalibracijskih noći sam uzimao p20,
a svaka noć daje **donju** granicu, pa je ispravno maksimum ili visoki percentil.
Podcjenjivao je četiri puta.

**14. Odgoda punjenja je počinjala prekasno.** Od 21 h se skupi samo 250 Wh
gubitka, jer je termostat do tada spremnik već napunio nakon večernjih tuševa. Mora
početi u 17 h, prije njih.

**15. Formula za `L` je miješala statistike.** `medijan(energije) / najdulja pauza`.
Ispravno je nizak percentil jednostrane procjene po ciklusu.

**16. Pomični prozor za `L` je pogoršao stvar** (+15 % do +54 %), jer ciklusi bez
potrošnje se grupiraju u periodima odsutnosti i kratki prozor ih ne sadrži.
Protuintuitivno, ali izmjereno.

**17. `hash()` u Pythonu je slučajan po procesu**, pa dataset nije bio
reproducibilan. Zamijenjeno sa SHA-256.

**18. Linearno pretraživanje događaja** u svakom koraku, oko milijardu usporedbi za
godinu. Predračun gustog rasporeda je smanjio vrijeme s 5 minuta na 75 sekundi po
arhetipu.

**19. Miješane jedinice u mojoj vlastitoj tablici** — dva stupca po uređaju u W, dva
za flotu u kW, bez oznake. Nečitljivo i uzrokovalo je pogrešno razumijevanje.

**20. Sabiranje p10 po uređaju kao flotni p10.** Pretpostavlja da svih 5000 uređaja
pogodi dno u istoj sekundi. Davalo je flotni p10 od nule. Flotni percentil se
računa na zbiru.

**21. Sintetska flota s dan-offsetom kroz cijelu godinu razmazuje sezonu.** Zato je
sezonska podjela u tablici 7.3 bezvrijedna (`lis-mar` i `apr-sep` ispadaju
identični). Sezonske brojke iz 7.2 su valjane. Popravak je ograničiti offset na
±30 dana.

**22. Zbunio sam kapacitet u energiji s kapacitetom u snazi.** Prva verzija analize
je davala 3,4 MW redukcije, jer nisam uračunao da se ne može skinuti snaga koja
ionako ne teče. Precjenjivanje otprilike dvostruko.

**23. Pomiješao sam dvije različite veličine pod imenom `E_full`** — korisnu
energiju iznad granice komfora (sezonski konstantnu) i ukupnu energiju punjenja iz
praznog (sezonski varijabilnu, +24 % zimi). Razdvojeno na `E_comfort` i `E_sink`.

**24. Opisao sam oporavak spremnika kao dvofazni** (89 minuta ničega, pa 56 minuta
korisnog), što vrijedi za savršeno izmiješan spremnik. U slojevitom je trošak
razmjeran od prve minute i nema mrtvog hoda.

### 8.3 Stvari koje je korisnik uhvatio, a ja propustio

**25. Donja granica iz uklopa termostata nije potrebna.** U trenutku kad naučiš da
ima mjesta, bojler ga već sam puni pri 2000 W. Nemaš što ponuditi.

**26. `E_shower` kao formula je neupitno loša.** Traži volumen tuša i željenu
temperaturu, oboje nepoznato. Cijeli lanac odluke radi bez nje.

**27. Statistička ponuda je ispravan pristup, ne kompromis.** Interval observer je
odgovarao na pogrešno pitanje za tržišnu stranu.

**28. Impuls uglavnom nije potreban ako postoji statistika.** Statistika nosi
glavninu; impuls uklanja samo koreliranu komponentu i za to je dovoljan uzorak od
nekoliko posto flote.

**29. Točnost vremenskih žigova je nebitna.** Za `E_hyst` od 22 minute i pauzu od
15 sati je nekoliko sekundi mrežnog šuma zanemarivo.

### 8.4 Četiri revizije mišljenja o probnom impulsu

Ovo vrijedi zapisati kao primjer kako se ocjena mijenja s mjerenjem.

| | procjena | zašto je bila takva |
|---|---|---|
| 1. | najvrjedniji dodatak arhitekturi | precijenio, prije ikakvog mjerenja |
| 2. | ne graditi | ispravno za redukciju, ali mjerio sam pogrešan proizvod |
| 3. | ključan za apsorpciju | ispravan smjer, ali pretpostavio dokaz po uređaju |
| 4. | mali rotirajući uzorak za kalibraciju | statistika nosi glavninu |

---

## 9. Otvorena pitanja

### 9.1 Tehnička, rješava simulator

- **Kad je uklop valjano sidro** — koliko sati mirnog perioda prije njega. Nije
  definirano, trenutno je 4 h uzeto ad hoc.
- **Kako se zna da je period bio miran.** Dok je relej zatvoren a termostat otvoren,
  potrošnja je nevidljiva. „Miran period" je djelomično pretpostavka, a od njega
  ovise `L`, `E_hyst` i valjanost uklopa.
- **Sezonska korekcija za negrijane instalacije** (11 % težine flote, `L`
  podcijenjen 11–16 %, opasan smjer za redukciju).
- **Korelirani ispadi konektivnosti** nisu u simulatoru. Bez njih su flotne brojke
  gornja granica.
- **Točnost izvedene potrošnje `D_k`** nije kvantificirana, a iz nje raste
  `E_reserve`.
- **Koliko košta jednočvorni pesimizam** u prihodu.
- **Dan umjesto mjeseca u procjeni korelirane varijance** (moj haircut je prestrog).
- **Kalibracijska noć dovoljno duga da zamijeni čekanje na godišnji odmor** —
  otključava apsorpciju mjesecima ranije.

### 9.2 Hardverska, provjerava se u pola sata na prvoj instalaciji

- **Gdje sonda termostata mjeri.** Jedini podešeni parametar u fizici. Pusti bojler
  da miruje i izmjeri trajanje grijanja: 22 minute znači da je model dobar, 8
  minuta znači da model treba mijenjati.
- **Daje li Shelly pouzdano mjerenje snage u 2–3 sekunde**, ako se ide na impulse.
- **Što električar zapisuje pri montaži**: volumen, snaga grijača, pozicija
  kotačića (≥60 °C, zapisano).
- **Prekapča li relej ili kontaktor.** Shelly 1PM Gen3 ima granicu prekapčanja
  2000 W, a grijač od 2 kW sjedi točno na njoj; 3 kW je prekoračuje. Trošenje
  kontakata pri čestom prekapčanju vodi u terenske intervencije, što je jedini
  trošak koji može uništiti model.

### 9.3 Odluke koje nisu donesene

- **Funkcija cilja optimizatora ne postoji.** Kako se vagaju arbitraža, naknada za
  kapacitet, trošak aktivacije, kazna za komfor i trošenje kontaktora — nema ni
  jedne formule.
- **Baseline za obračun dostave.** Kako se dokazuje redukcija za teret koji je 83 %
  vremena ionako isključen.
- **Što Boost točno radi i tko plaća tu energiju.**
- **Alarm za zavaren termostat** — vidi se kao snaga koja teče a isklop nikad ne
  dođe. Sigurnosni događaj, trenutno nigdje.
- **Čiji je relej** ako korisnik odustane nakon šest mjeseci.
- **Rezerva komfora: jedan tuš ili dva.** Razlika je gotovo dvostruka u veličini
  proizvoda (69 % spremnika prema 38 %).
- **Ukupni konzervativizam nije auditiran.** Šest neovisno ispravnih sigurnosnih
  margina se množi i mogu pojesti cijeli proizvod. Treba ih ugađati kao jedan
  sustav protiv jedne izmjerene stope hladnih tuševa, a ne kao šest neovisnih
  vijaka.

### 9.4 Vanjski blokeri

- Zahtijeva li HOPS ovjerena mjerila i koja je zahtijevana rezolucija telemetrije.
- Pravila prekvalifikacije za agregirane portfelje potrošnje.
- Postoje li dinamičke tarife za domaćinstva u Hrvatskoj.
- Koji dobavljač nosi poziciju u obračunskoj grupi.
- Stvarne cijene s HOPS tendera, da zamijene procjenu od 40–150 €/uređaj/god.
- **Postoji li proizvod za preuzimanje viška**, a ne samo za redukciju. Do sada je
  cijeli plan bio okrenut na redukciju, a podaci kažu da je jači proizvod u drugom
  smjeru. To pitanje treba postaviti zajedno s onim o mjerilima.

---

## 10. Preporučeni redoslijed

### 10.1 Odmah, ne treba nikakav vanjski odgovor

1. **Popraviti sezonsku korekciju `L` za negrijane instalacije.** Podcjenjivanje je
   opasan smjer za redukciju i pogađa 11 % flote.
2. **Kalibracijska noć koja zamjenjuje čekanje na godišnji odmor.** Otključava
   apsorpciju — četiri puta veći proizvod — mjesecima ranije.
3. **Modelirati korelirane ispade konektivnosti.** Bez toga su sve flotne brojke
   gornja granica, a ponude prema TSO-u moraju biti donja.
4. **Definirati funkciju cilja optimizatora.** Trenutno je nema, a bez nje se ne
   može donijeti nijedna odluka o dispečiranju.
5. **Audit ukupnog konzervativizma** protiv jedne ciljne stope hladnih tuševa.

### 10.2 Jedna instalacija u Prečkom

6. Provjeriti sondu termostata (jedan podešeni parametar u fizici).
7. Izmjeriti stvarni `L`, `E_hyst`, kapacitet.
8. Provjeriti javljaju li se sidra kako je predviđeno.
9. Zapisati nazivne podatke i postaviti kotačić na ≥60 °C.
10. Početi skupljati stvarnu distribuciju potrošnji, koja zamjenjuje izmišljene
    profile u simulatoru.

### 10.3 Prije narudžbe hardvera za fazu 1

11. Odgovoriti na pitanja iz 9.4, u pisanom obliku.
12. **Istražiti prodaju u portfelj postojećeg BSP-a**, jer to skida i prag od 1 MW i
    pitanje ovjerenih mjerila s kritičnog puta i omogućuje prihod pri 500 uređaja.

### 10.4 Što ne graditi

PINN, Fokker–Planck, PEM na uređaju, GEKKO, EKF. Svaki je obranjiv u radu i nijedan
ne mijenja odluku koju treba donijeti u sljedećih 18 mjeseci.

---

## 11. Jedna stranica za pamćenje

```
PROIZVOD          apsorpcija prije redukcije, 2–3× veća i bez rizika komfora
PRVI MEGAVAT      ~2.400 uređaja, noćna apsorpcija 00–05
STANJE            manjak ispod isklopa, u Wh, nikad temperatura
SIDRO             isklop termostata: egzaktno, besplatno, dnevno
KALIBRACIJA       odgoda punjenja od 17 h, grijanje 01–05 h, jednom u 7 dana
NAJOSJETLJIVIJE   L mora biti TOČAN; zahtijeva period odsutnosti korisnika
TRŽIŠTE           vjerojatnosna ponuda, p1 flotnog zbira, ne garancija
KOMFOR            konzervativno po uređaju, tvrda granica, ne poolati
FLOTA             iznad 1.000 uređaja pouzdanost više ne raste, samo količina
NE NUDITI         apsorpciju dok l_confident nije podignut
MONTAŽA           kotačić na 60 °C zapisan, DIN kontaktor, nazivni podaci
ZABRANJENO        tvrditi dezinfekciju; iznad 60 °C; simetričan cjelodnevni proizvod
NEIZVJESNOST      faktor 1,5 dok profili potrošnje nisu izmjereni
```
