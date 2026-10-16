# Fonti e formati

Ricognizione del 2026-10-15, fatta leggendo gli elenchi delle cartelle e alcuni
file di `services.swpc.noaa.gov`, e le pagine ufficiali di SWPC. In T1 (stesso
giorno) le affermazioni sono state controllate sui file scaricati per intero e
sulle fixture in `tests/fixtures/`: dove c'è scritto **verificato**, il riferimento
è la fixture indicata. Dove una riga dice ancora **ipotesi**, va verificata
prima di scriverci codice sopra. Quando una tappa verifica o smentisce
qualcosa, aggiorna questo file.

## Cartelle

- `https://services.swpc.noaa.gov/json/`: tra gli altri `planetary_k_index_1m.json`,
  `ovation_aurora_latest.json`, `solar_regions.json`, `f107_cm_flux.json`,
  `icao-space-weather-advisories.json`; sottocartelle `rtsw/`, `goes/`, `ace/`,
  `geospace/`, `lists/`, `solar-cycle/`, `stereo/`.
- `https://services.swpc.noaa.gov/products/`: `alerts.json`,
  `noaa-planetary-k-index.json`, `noaa-planetary-k-index-forecast.json`,
  `kyoto-dst.json`, `noaa-scales.json`, `10cm-flux-30-day.json`; sottocartella
  `summary/` (`10cm-flux.json`, `solar-wind-mag-field.json`,
  `solar-wind-speed.json`).
- `https://services.swpc.noaa.gov/text/`: `3-day-forecast.txt`,
  `3-day-geomag-forecast.txt`, `27-day-outlook.txt`,
  `drap_global_frequencies.txt`, `srs.txt`, `discussion.txt`, e altri.
- `https://services.swpc.noaa.gov/text/scn/` contiene **file di esempio
  ufficiali** allegati alle SCN, non i testi delle SCN:
  - `fy22-kp/` (2022-09-22): esempi del **vecchio formato** di Kp 3 ore e
    previsione, più Kp 1 minuto, 3-day forecast e altri testi. Copiati in
    `tests/fixtures/` quelli utili (vedi il README delle fixture).
  - `fy26-03/` (2026-02-27): esempi del **nuovo formato** (array di oggetti)
    di Kp 3 ore e previsione, Dst, `10cm-flux-30-day`, `10cm-flux` e dei due
    riepiloghi del vento solare. Stesso formato delle fixture registrate: non
    copiati.

Tutti i file registrati il 2026-10-15 sono UTF-8 senza BOM, con righe chiuse
da `\n`; i JSON sono su una sola riga, senza `\n` finale; i testi finiscono
con `\n`. Il server dà `Last-Modified`, `ETag` e `Cache-Control: max-age=60`.

## Indici

- **Kp 3 ore** (`/products/noaa-planetary-k-index.json`, fixture
  `kp-3h/2026-10-15.json`), **verificato**: array di 61 oggetti, ordine
  crescente, 7 giorni e mezzo a passo di 3 ore. Formato compatto, numeri con
  due decimali (`"Kp":1.00`):
  `{"time_tag":"2026-10-08T00:00:00","Kp":1.00,"a_running":4,"station_count":8}`.
  `time_tag` senza `Z`: va inteso UTC (**ipotesi** ragionevole, da scrivere
  nella docstring).
- **Previsione del Kp** (`noaa-planetary-k-index-forecast.json`),
  **verificato**: 81 oggetti `{time_tag, kp, observed, noaa_scale}`, da 7
  giorni prima a 3 giorni dopo. `observed` vale `"observed"` (61),
  `"estimated"` (3) o `"predicted"` (17); `noaa_scale` è `null` o una
  stringa come `"G1"`, `"G3"`. Attenzione: qui la chiave è `kp`, nel Kp 3 ore
  è `Kp`.
  Le voci `estimated` possono stare **nel futuro**: registrando alle 17:57 UTC
  c'erano già quelle delle 18:00 e delle 21:00. Per questo il `data_time` della
  previsione è l'ultima voce `observed`.
- **Formato precedente** (fino a circa il 2026-03-31, SCN 26-21),
  **verificato** sugli esempi ufficiali del 2022 (`kp-3h/2022-09-22-sample.json`,
  `kp-forecast/2022-09-22-sample.json`): array di array, prima riga con i nomi
  delle colonne (gli stessi del formato nuovo), poi una riga per record con
  i numeri tra virgolette e `null` senza virgolette. Formato compatto.
  `time_tag` con lo spazio al posto della `T`: nel Kp 3 ore con i millisecondi
  (`"2022-09-15 00:00:00.000"`), nella previsione senza
  (`"2022-07-27 00:00:00"`). Riguardava anche Dst, `10cm-flux-30-day` e i
  riepiloghi del vento solare: per Dst e flusso non c'è un esempio reale, le
  fixture `*-built.json` sono costruite da quelle registrate. Che il loro
  `time_tag` non avesse i millisecondi è **ipotesi**: il parser deve
  accettare entrambe le forme.
- **Kp 1 minuto** (`/json/planetary_k_index_1m.json`, fixture
  `kp-1m/2026-10-15.json`), **verificato**: 358 oggetti in ordine crescente,
  circa 6 ore. `{"time_tag":"2026-10-15T11:51:00","kp_index":3,"estimated_kp":3.00,"kp":"3Z"}`.
  Il suffisso di `kp` indica il terzo: `Z` intero, `P` più un terzo, `M` meno
  un terzo (0.33 → `"0P"`, 0.67 → `"1M"`, 2.67 → `"3M"`, 3.00 → `"3Z"`), e
  `kp_index` è la cifra di `kp`. L'esempio ufficiale del 2022
  (`fy22-kp/10-102_planetary_k_index_1m_sample.json`) **non è usabile**: ha un
  BOM UTF-8 e un a capo `\r\n` ogni ~2 KB anche a metà parola, quindi non è
  JSON valido.
- **Dst** (`kyoto-dst.json`), **verificato**: 168 oggetti orari
  `{"time_tag":"2026-10-08T18:00:00","dst":-17}`, 7 giorni.
- **F10.7 30 giorni** (`10cm-flux-30-day.json`), **verificato**: 30 oggetti
  `{"time_tag":"2026-09-15T20:00:00","flux":107}`, uno al giorno alle 20 UTC,
  flusso intero.
- **Scale NOAA** (`noaa-scales.json`, fixture `noaa-scales/2026-10-15.json`),
  **verificato** nella forma: un oggetto con chiavi `"-1"`, `"0"`, `"1"`, `"2"`,
  `"3"`, ognuna con `DateStamp` (`"2026-10-15"`), `TimeStamp` (`"17:50:00"`) e
  i gruppi `R` (`Scale`, `Text`, `MinorProb`, `MajorProb`), `S` (`Scale`,
  `Text`, `Prob`), `G` (`Scale`, `Text`). Tutti i valori sono stringhe o
  `null` (`"Scale": "0"`, `"MinorProb": "20"`). **Ipotesi** dal confronto
  delle date: `-1` sono le scale osservate nelle 24 ore precedenti, `0` quelle
  attuali, `1`–`3` la previsione per oggi e i due giorni seguenti (con le
  probabilità e senza `Scale` per R e S). `DateStamp`/`TimeStamp` sono letti come UTC:
  nella fixture la voce `0` dice `17:54:00` ed è stata registrata alle 17:57
  UTC (indizio, non documentazione).

## Vento solare (RTSW)

- `/json/rtsw/rtsw_mag_1m.json` (~1,4 MB) e `/json/rtsw/rtsw_wind_1m.json`
  (~2,4 MB), fixture ridotte `rtsw-*-1m/2026-10-15.json`, **verificato**:
  array di oggetti in ordine **decrescente** (il più recente per primo),
  **24 ore**. Campi del mag: `time_tag`, `active`, `source`, `range`, `scale`,
  `sensitivity`, `manual_mode`, `sample_size`, `bt`, `b{x,y,z}_{gse,gsm}`,
  `theta_*`, `phi_*`, `max_telemetry_flag`, `max_data_flag`,
  `overall_quality`. Del plasma: `proton_*` e `alpha_*` (velocità, densità,
  temperatura, componenti in GSE e GSM, `*_sample_size`), sette flag `max_*`,
  `overall_quality`. Molti campi possono essere `null` (le componenti della
  velocità di ACE, tutti gli `alpha_*`); `max_data_flag` può valere `-9999`.
- Formato JSON di Python (separatori `", "` e `": "`).
- **Fonti** il 2026-10-15: `SOLAR1` (sempre `active: true`), `ACE` e `IMAP`
  (sempre `active: false`). Per istante ci sono uno o due record: di solito
  SOLAR1 e ACE insieme. Ci sono minuti con **solo record inattivi** (ACE da
  solo, 15 nel mag e 223 nel plasma), quindi "il record attivo per istante"
  può mancare.
- **IMAP** ha `time_tag` non allineati al minuto (quasi sempre a `:01`
  secondi, a volte altri), quindi non condivide mai l'istante con le altre
  fonti; nel giorno registrato copre circa dalle 20:27 alle 15:54.
- Dal 2026-06-30 la fonte primaria è **SOLAR-1** (SWFO-L1), con ACE di
  riserva; DSCOVR non è più elaborato.
- **Verificato in T3** sulle fixture ridotte (223 record mag, 220 plasma):
  - i secondi di IMAP dipendono dal file: nel mag `:01` (21 record) e `:09`
    (uno), nel plasma sempre `:03` (28 record);
  - nessun istante ha due record attivi; nel mag 23 istanti su 137 non hanno
    il record attivo (22 di solo IMAP, uno di solo ACE alle 21:01 del
    14), nel plasma 41 su 134 (28 di solo IMAP, 13 di solo ACE);
  - `max_data_flag` vale `-9999` per SOLAR1 e ACE nel mag, `0` per IMAP; nel
    plasma è sempre `0`. Che `-9999` sia un valore di riempimento
    ("flag non disponibile") è **ipotesi**: il parser lo tiene com'è;
  - `range`, `scale` e `sensitivity` del mag sono sempre `null`: il tipo
    non si può dedurre e il parser non li legge;
  - ACE e IMAP non danno le componenti della velocità (`proton_v*` a
    `null`); gli `alpha_*` sono `null` per tutte le fonti;
  - nei campi fisici non compare mai `-9999`: che un valore mancante sia
    sempre `null` è **ipotesi**. Il parser rifiuta (`ParseError`) valori
    impossibili: `bt`, velocità, densità e temperatura negative, `theta_*`
    fuori da -90…90, `phi_*` fuori da 0…360 (nella fixture `phi` va da 4,0 a
    359,8);
  - `overall_quality`, `max_telemetry_flag` e `sample_size` (60 nel mag, 1
    nel plasma) hanno sempre lo stesso valore: il significato dei flag non è
    documentato.
- **Scelte del modello** (T3): i record sono riordinati dal più vecchio,
  tenendo l'ordine del file fra quelli dello stesso istante; il record
  attivo di un istante è quello con `active: true` (se fossero due, vince il
  primo nel file); un istante senza record attivo resta senza, non si
  ripiega su un'altra fonte. Le fonti sconosciute restano stringhe.
  `data_time` è l'ultimo `time_tag` di qualunque fonte; la freschezza della
  sola fonte attiva è `latest_active().time`.

## GOES

- `/json/goes/primary/` e `/secondary/`, file `*-6-hour`, `*-1-day`,
  `*-3-day`, `*-7-day`.
- `xrays-1-day.json` (fixture ridotta `goes-xrays-1-day/2026-10-15.json`),
  **verificato**: ordine crescente, un minuto di passo, due record per
  istante, uno per banda (`energy`: `"0.05-0.4nm"` e `"0.1-0.8nm"`). Campi:
  `time_tag` (con `Z`), `satellite` (18), `flux`, `observed_flux`,
  `electron_correction`, `electron_contaminaton` (scritto così nella fonte:
  il refuso è il nome vero del campo). Formato JSON di Python.
- La classe del brillamento (A/B/C/M/X) si calcola dal flusso della banda
  0.1–0.8 nm: A < 1e-7, B < 1e-6, C < 1e-5, M < 1e-4, X ≥ 1e-4 W/m², con il
  moltiplicatore (M2.5 = 2,5e-5). Il massimo del giorno registrato è circa
  C5.0 alle 15:55 (non tenuto dalla riduzione; nella fixture il massimo è
  circa C3.9).
- `integral-protons-1-day.json` (fixture ridotta), **verificato**:
  `{"time_tag":…,"satellite":18,"flux":5.38,"energy":">=1 MeV"}`, ordine
  crescente, passo di 5 minuti (qualche istante manca), otto energie per
  istante: `>=1`, `>=5`, `>=10`, `>=30`, `>=50`, `>=60`, `>=100`,
  `>=500 MeV`.
- **Verificato in T3** sulle fixture:
  - nei raggi X `flux` = `observed_flux` − `electron_correction`, ma con un
    **minimo** di 1e-9 (scritto `9.999999717180685e-10`, cioè 1e-9 in
    precisione singola): nei 6 record in cui la differenza è più bassa, o
    negativa, `flux` vale quel minimo. Succede solo nella banda
    0,05–0,4 nm, sempre con `electron_contaminaton: true`. Che il minimo
    valga sempre è **ipotesi**: il parser non controlla il segno del flusso,
    e la classe del brillamento esce `None` per un flusso nullo o negativo;
  - `electron_contaminaton` è `true` solo nella banda corta (100 record su
    129), mai nella lunga;
  - nei protoni le otto energie di un istante sono in ordine di stringa
    (`>=1`, `>=10`, `>=100`, `>=30`, `>=5`, `>=50`, `>=500`, `>=60`), non di
    soglia: il parser ricava la soglia in MeV dall'etichetta `>=N MeV` e
    rifiuta (`ParseError`) un'etichetta di altra forma.
- **Ipotesi**: i file `*-6-hour`, `*-3-day`, `*-7-day` e la cartella
  `secondary/` hanno lo stesso formato dei file di un giorno del primario
  (gli unici registrati); i parser li accettano con `source_url=`.
- **Verificato** sulle pagine SWPC (lette il 2026-10-16):
  - `products/goes-proton-flux`: i file `integral-protons` danno flussi
    integrali mediati su 5 minuti in protoni/(cm² s sr) (= pfu) per le
    soglie ≥1, 5, 10, 30, 50, 60, 100 e 500 MeV, le stesse delle fixture;
    soglie degli avvisi 10…100 000 pfu a ≥10 MeV e 1 pfu a ≥100 MeV;
  - `products/goes-x-ray-flux`: medie di 1 minuto nelle bande 0,1–0,8 nm e
    0,05–0,4 nm, dati del satellite primario e secondario; massimo di un
    evento = minuto del picco;
  - `phenomena/solar-flares-radio-blackouts`: la classe si definisce sul
    picco della banda 0,1–0,8 nm, in W/m², con A da 10⁻⁸, B da 10⁻⁷, C da
    10⁻⁶, M da 10⁻⁵, X da 10⁻⁴.
- **Classe del brillamento** (T3): il moltiplicatore è **troncato** a un
  decimale (3,95e-6 → C3.9; 9,99e-6 → C9.9, mai C10.0), calcolato sulla forma
  decimale più corta del flusso, così 2,3e-5 dà M2.3. Che SWPC tronchi invece
  di arrotondare resta **ipotesi** (le pagine SWPC non lo dicono): il
  troncamento è scelto perché tiene la
  lettera coerente con le soglie. La classe si calcola solo sulla banda
  0,1–0,8 nm; X non ha tetto (1,2e-3 → X12.0).

## Avvisi

- `/products/alerts.json` (fixture `alerts/2026-10-15.json`), **verificato**:
  81 oggetti `{product_id, issue_datetime, message}`, ordine decrescente,
  circa 30 giorni. `issue_datetime` nel formato `YYYY-MM-DD HH:MM:SS.mmm`.
- `message` mescola gli a capo: in **ogni** messaggio le prime righe
  (intestazione e riga vuota) finiscono con `\r\n`, il resto anche con `\n`.
  Il parser deve accettare entrambi.
- Prime tre righe sempre presenti: `Space Weather Message Code: WARK04`,
  `Serial Number: 5435`, `Issue Time: 2026 Oct 13 2058 UTC`. Poi il titolo
  (`ALERT:`, `WARNING:`, `EXTENDED WARNING:`, `WATCH:`, `CONTINUED ALERT:`,
  `CANCEL WATCH:`, `SUMMARY:`) e campi come `Valid From:`, `Valid To:`,
  `Now Valid Until:`, `Threshold Reached:`, `Synoptic Period:`,
  `Active Warning:`, `Begin Time:`, `End Time:`, `Maximum Time:`,
  `Extension to Serial Number:`, `Continuation of Serial Number:`,
  `Cancel Serial Number:`, `Comment:`, `Potential Impacts:`.
- **Varianti da gestire**: `NOAA Scale:` (26 volte) e `Noaa Scale:` (25);
  `Warning Condition:` e `Warning Conditions:`; `Estimate Velocity:` (non
  "Estimated").
- **Due famiglie di codici.** La tabella ufficiale
  (`https://www.spaceweather.gov/content/subscription-services`) usa codici
  lunghi come `ALTK05`, `WARK04`, `WATA20`; i `product_id` di `alerts.json`
  sono corti. **Corrispondenza verificata** sul testo dei 81 messaggi (ogni
  codice corto ha sempre lo stesso codice lungo):

  | Corto | Lungo | Corto | Lungo |
  |---|---|---|---|
  | `K04W`…`K07W` | `WARK04`…`WARK07` | `TIIA` | `ALTTP2` |
  | `K04A`…`K07A` | `ALTK04`…`ALTK07` | `TIVA` | `ALTTP4` |
  | `A20F` | `WATA20` | `XM5A` | `ALTXMF` |
  | `A30F` | `WATA30` | `XM5S` | `SUMXM5` |
  | `EF3A` | `ALTEF3` | `SGIW` | `WARSUD` |
  | `MSIS` | `SUMSUD` | `BHIS` | `SUM10R` |

  Nella tabella ufficiale `ATLK04` compare scritto così (probabile refuso per
  `ALTK04`). Gli esempi del 2022 dentro `swpclib` (`A20F`, `K05W`, `K05A`)
  sono coerenti.

## Bollettini testuali

Fixture `3-day-forecast/`, `geomag-forecast/`, `27-day-outlook/`,
**verificato**:

- Intestazione comune: `:Product: …` e `:Issued: 2026 Oct 15 1230 UTC`, poi
  commenti con `#`. Il nome del prodotto cambia da file a file:
  `3-Day Forecast`, `Geomagnetic Forecast` (per `3-day-geomag-forecast.txt`),
  `27-day Space Weather Outlook Table 27DO.txt`.
- Le tabelle hanno **spazi in coda** alle righe.
- `3-day-forecast.txt`: sezioni `A.` (frase sul Kp massimo osservato e
  previsto, poi `NOAA Kp index breakdown Oct 15-Oct 17 2026` con otto righe
  `00-03UT` … `21-00UT` e tre colonne di Kp), `B.` (riga `S1 or greater` con
  tre percentuali) e `C.` (righe `R1-R2` e `R3 or greater`). Ogni sezione ha
  un `Rationale:` su più righe. Il Kp massimo osservato può essere scritto
  intero (`was 3 (below NOAA`), con la frase spezzata su due righe. Nell'esempio
  del 2022 (`3-day-forecast/2022-09-22-sample.txt`) una cella della tabella è
  `5.33 (G1)`: la scala NOAA si aggiunge accanto al valore.
- `3-day-geomag-forecast.txt`: `Observed Ap 13 Oct 013`, `Estimated Ap 14 Oct 011`,
  `Predicted Ap 15 Oct-17 Oct 010-008-005`, probabilità come `Active 25/20/15`
  (attiva, tempesta minore, moderata, forte-estrema), poi la tabella dei Kp
  con lo stesso schema di righe del 3-day forecast.
- `27-day-outlook.txt`: dopo i commenti, 27 righe a larghezza fissa,
  `2026 Oct 12     120          16          4` = data, flusso a 10,7 cm, Ap,
  Kp massimo; l'emissione del 2026-10-12 parte dal giorno stesso.

## Griglie

- **OVATION** (`/json/ovation_aurora_latest.json`, ~0,9 MB, fixture ridotta
  `ovation-aurora/2026-10-15.json`), **verificato** sul file intero: chiavi
  `Observation Time`, `Forecast Time` (con `Z`), `Data Format`
  (`"[Longitude, Latitude, Aurora]"`), `coordinates`. `coordinates` ha 65 160
  terne di interi: longitudine 0–359 come ciclo esterno, latitudine -90…90 come
  ciclo interno, passo 1 (360×181). Valori 0–35 il giorno registrato. Che il
  valore sia la probabilità di aurora in percento resta **ipotesi**: il file non
  lo dice. La fixture tiene 15 longitudini intere (0, 1, 30, 60, … 330, 358,
  359), quindi **non** è una griglia completa: i test della griglia intera
  vanno costruiti nel codice.
- **D-RAP** (`/text/drap_global_frequencies.txt`, fixture `drap/2026-10-15.txt`
  intera), **verificato**: commenti `#` con `Product Valid At : 2026-10-15 17:47 UTC`,
  `Estimated Recovery Time : No Estimate`, `X-RAY Message :`,
  `X-RAY Warning :`, `Proton Message :`, `Proton Warning :` (gli avvisi
  possono essere vuoti); poi una riga di intestazione con 90 longitudini da
  -178 a 178 passo 4, una riga tratteggiata e 90 righe di latitudine da 89 a
  -89 passo 2, nella forma ` 89 |  0.0  0.0 …`, frequenze in MHz con un
  decimale.
- Per il GeoTIFF: le coordinate sono centri di cella su griglia regolare
  lat/lon (EPSG:4326). La longitudine di OVATION (0–359) va ruotata a
  -180…180 per l'uso su mappa: l'export lo fa, il modello conserva i dati
  come arrivano.

## Cambiamenti noti (SCN)

- **SCN 26-21** (2026-03-02): nuovi formati JSON dal 2026-03-31 circa, vecchi
  deprecati dal 2026-04-30.
- **Vento solare** (2026-06-30): fine di DSCOVR, SOLAR-1 primario, ACE di
  riserva; IMAP in arrivo. Il 2026-10-15 i record IMAP sono già nei file
  RTSW, inattivi.
- **SCN 26-39**: chiusura di GeoAlert (`geoalert.txt`) prevista il 2026-05-19,
  ma il file era ancora presente il 2026-10-15. Fuori dalla prima versione.
- **SCN 26-35**: chiusura del modello TEC CTIPe, sostituito da GloTEC.
- Le pagine di contenuto di `swpc.noaa.gov` rimandano a `www.spaceweather.gov`;
  `services.swpc.noaa.gov` risponde ancora. Avvisi e archivio:
  `https://www.weather.gov/notification/`; `services.swpc.noaa.gov/text/scn/`
  contiene i file di esempio delle SCN (vedi "Cartelle").

## Lezioni da chi usa già questi dati

- SWPC a volte serve un JSON **troncato** mentre lo riscrive: è
  `SourceNotReady`, non un errore del parser.
- Una fonte NOAA spostata può rispondere con un redirect verso una pagina
  HTML: chi segue i redirect riceve HTML al posto dei dati
  (`UnexpectedContent`).
- La data di modifica di un file non dice l'età del contenuto: si guarda il
  tempo scritto dentro.

## Librerie esistenti (2026-10-15)

Non ne abbiamo trovata una che copra tutto con modelli tipizzati, parsing dei
messaggi e dei bollettini, ed export delle griglie. Frammenti:

- `sunpy`: solo le previsioni del ciclo solare (macchie, F10.7).
- `swvo` (GFZ, Apache-2.0): da SWPC solo Kp e F10.7.
- `spaceweather` (pyspaceweather): indici da Celestrak, GFZ, OMNI; non SWPC.
- `solar-mcp`, `spaceweather-mcp`: server MCP, non librerie.

### `swpclib` e `nws-aurora` (misurate in T0, 2026-10-15)

Lette dai sorgenti su PyPI. Nessuna delle due copre una parte rilevante di
`SPEC.md`: si va avanti.

- **`swpclib` 4.3.7** (MIT, 2024-04-18, dipende da `aiohttp`, `pillow`,
  `click`; il README dice "Features: TODO"). Una classe `Runner` asincrona
  che scarica e restituisce **dizionari** senza tipi: F10.7
  (`/json/f107_cm_flux.json`), K di Boulder, A di Fredericksburg previsto,
  macchie solari osservate, Kp 1 minuto, `solar_probabilities.json`,
  `alerts.json`, e animazioni GIF (SUVI, OVATION, LASCO, D-RAP) montate con
  Pillow. Gli errori sono **ingoiati**: `print(repr(e))` e un valore `None`.
  Le date dei messaggi restano senza fuso (`datetime.now()` confrontato con
  orari UTC). Non tocca Kp 3 ore, Dst, scale, RTSW, GOES, bollettini,
  griglie, né i formati nuovi del 2026. Un solo test.
- **`nws-aurora` 0.0.6** (MIT, 2024-09-18, dipende da `requests`, `bs4`,
  `geojson`, `pytz`, `click`). Solo aurora: elenco delle immagini OVATION
  (raschiando l'indice HTML della cartella), griglia OVATION come
  `FeatureCollection` di **punti** con longitudine 0–359 così com'è, e
  `aurora-nowcast-hemi-power.txt` letto saltando 16 righe fisse. Nessun tipo,
  nessuna gestione degli errori.
- **Nome**: `swpc-kit` (e `swpc_kit`, `swpckit`) libero su PyPI il
  2026-10-15 (risposta 404 dell'API JSON). PyPI può comunque rifiutare un
  nome alla prima pubblicazione: si ricontrolla prima di pubblicare.

Due cose utili lette nei loro sorgenti, da fonti **non ufficiali**:

- `swpclib` contiene tre esempi di `alerts.json` del 2022-09-27, citati in
  "Avvisi" sopra.
- `nws-aurora` contiene una griglia OVATION del 2024-09-18 già convertita:
  65 160 punti, longitudine 0–359 (360 valori), latitudine -90…90 (181
  valori). Coerente con la griglia verificata in T1.
