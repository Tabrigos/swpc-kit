# Fonti e formati

Ricognizione del 2026-10-15, fatta leggendo gli elenchi delle cartelle e alcuni
file di `services.swpc.noaa.gov`, e le pagine ufficiali di SWPC. Le letture
sono passate da uno strumento che a volte riassume invece di citare: dove una
riga dice **ipotesi**, va verificata su una fixture prima di scriverci codice
sopra. Quando una tappa verifica o smentisce qualcosa, aggiorna questo file.

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
  `drap_global_frequencies.txt`, `srs.txt`, `discussion.txt`, e altri; `scn/`
  contiene le Service Change Notices.

## Indici

- **Kp 3 ore** (`/products/noaa-planetary-k-index.json`): dal 2026 array di
  oggetti, circa 7 giorni (61 elementi). Esempio letto:
  `{"time_tag":"2026-10-08T00:00:00","Kp":1.00,"a_running":4,"station_count":8}`.
  Nota: `time_tag` senza `Z`, va inteso UTC (**ipotesi** ragionevole, da
  scrivere nella docstring).
- **Formato precedente** (fino a circa il 2026-03-31, SCN 26-21): array di
  array, prima riga con i nomi delle colonne, valori numerici tra virgolette.
  Riguardava Kp 3 ore e previsione, Dst di Kyoto, `10cm-flux-30-day` e i
  riepiloghi del vento solare. Non abbiamo un file reale del vecchio formato:
  la fixture si costruisce a mano dalla descrizione, e lo si dichiara.
- **Kp 1 minuto** (`/json/planetary_k_index_1m.json`):
  `{"time_tag":"2026-10-15T11:02:00","kp_index":2,"estimated_kp":2.00,"kp":"2Z"}`.
  Il significato del suffisso di `kp` ("2Z", e "+"/"-" nei terzi) è **ipotesi**.

## Vento solare (RTSW)

- `/json/rtsw/rtsw_mag_1m.json` (~1,4 MB) e `/json/rtsw/rtsw_wind_1m.json`
  (~2,3 MB): array di oggetti con `time_tag`, `active`, `source`, e i campi
  fisici (`bt`, `bx_gsm`… / `proton_speed`, `proton_density`,
  `proton_temperature`…) più flag di qualità (`overall_quality`, `max_*`).
- Dal 2026-06-30 la fonte primaria è **SOLAR-1** (SWFO-L1), con ACE di
  riserva; DSCOVR non è più elaborato. Nello stesso file ci sono record di
  fonti diverse per lo stesso istante: `active: true` indica quella in uso.
  Il 2026-10-15 il mag aveva `"source":"SOLAR1","active":true`, il plasma
  aveva in testa `"source":"ACE","active":false`.
- La profondità temporale dei file (1 giorno? 7?) è **ipotesi**: da misurare.

## GOES

- `/json/goes/primary/` e `/secondary/`, file `*-6-hour`, `*-1-day`,
  `*-3-day`, `*-7-day`.
- `xrays-7-day.json`: due record per istante, uno per banda (`energy`:
  `"0.05-0.4nm"` e `"0.1-0.8nm"`). Campi: `time_tag` (con `Z`), `satellite`,
  `flux`, `observed_flux`, `electron_correction`, `electron_contaminaton`
  (scritto così nella fonte: il refuso è il nome vero del campo).
- La classe del brillamento (A/B/C/M/X) si calcola dal flusso della banda
  0.1–0.8 nm: A < 1e-7, B < 1e-6, C < 1e-5, M < 1e-4, X ≥ 1e-4 W/m², con il
  moltiplicatore (M2.5 = 2,5e-5).
- `integral-protons-1-day.json`: `{"time_tag":…,"satellite":18,"flux":6.52,"energy":">=1 MeV"}`,
  energie ≥1, ≥10, ≥100 MeV (e altre, **ipotesi**).

## Avvisi

- `/products/alerts.json`: array di oggetti `{product_id, issue_datetime, message}`;
  `issue_datetime` nel formato `YYYY-MM-DD HH:MM:SS.mmm`; `message` è il testo
  intero, su più righe, con intestazione (codice del messaggio, numero di
  serie, ora di emissione) e campi come `Valid From:` / `Valid To:`. Il testo
  esatto delle intestazioni è **ipotesi** finché non c'è la fixture.
- **Due famiglie di codici.** La tabella ufficiale
  (`https://www.spaceweather.gov/content/subscription-services`) usa codici
  come `ALTK05`, `WARK04`, `WATA20`, `ALTEF3`, `ALTXMF`, `SUMX01`, `ALTPX1`,
  `ALTTP2`. I `product_id` di `alerts.json` sono invece corti: il 2026-10-15
  c'erano `K04W`, `K05A`, `EF3A`, `TIIA`, `A20F`, `A30F`, `K06A`, `K07A`,
  `XM5S`, `XM5A`, `K06W`, `TIVA`, `K07W`, `MSIS`, `BHIS`, `SGIW`.
- **Corrispondenza, ipotesi da verificare** sul testo dei messaggi (che
  dovrebbe contenere il codice lungo): `K0nW` = `WARK0n`, `K0nA` = `ALTK0n`,
  `EF3A` = `ALTEF3`, `TIIA`/`TIVA` = `ALTTP2`/`ALTTP4`, `XM5A`/`XM5S` =
  `ALTXMF`/`SUMXM5`, `A20F`/`A30F` = `WATA20`/`WATA30`, `SGIW` = `WARSUD`.
  `MSIS` e `BHIS`: significato sconosciuto. Nella tabella ufficiale `ATLK04`
  compare scritto così (probabile refuso per `ALTK04`).
- **Indizi dai messaggi del 2022** (esempi copiati nel sorgente di `swpclib`,
  fonte non ufficiale, quindi ancora **ipotesi**): `A20F` → `WATA20`,
  `K05W` → `WARK05`, `K05A` → `ALTK05`. Il testo va a capo con `\r\n` e
  inizia con `Space Weather Message Code: …`, `Serial Number: …`,
  `Issue Time: 2022 Sep 27 1957 UTC`; poi righe come `ALERT: …`,
  `WARNING: …` (o `EXTENDED WARNING: …` con `Extension to Serial Number:`),
  `WATCH: …`, `Threshold Reached:`, `Synoptic Period:`, `Valid From:`,
  `Valid Until:` / `Now Valid Until:`, `Warning Condition:`,
  `Active Warning: Yes`, `NOAA Scale: G1 - Minor`, `Potential Impacts:`. Nel
  JSON grezzo la barra compariva come `\/`, che il parser JSON decodifica in
  `/`. Da confermare sulla fixture di T1.

## Bollettini testuali

- Intestazione comune: righe che iniziano con `:Product:` e `:Issued:`
  (`:Issued: 2026 Oct 15 1230 UTC`), commenti con `#`.
- `3-day-forecast.txt`: sezioni A (attività geomagnetica, tabella dei Kp
  previsti per fasce di 3 ore su 3 giorni), B (radiazione solare, probabilità
  S1 o più), C (radio blackout, probabilità R1–R2 e R3 o più).
- `3-day-geomag-forecast.txt`: Ap previsti, probabilità di attività, tempesta
  minore, moderata, forte/estrema, tabella dei Kp.
- `27-day-outlook.txt`: righe a larghezza fissa, per esempio
  `2026 Oct 12     120          16          4` = data, flusso a 10,7 cm, Ap,
  Kp massimo.

## Griglie

- **OVATION** (`/json/ovation_aurora_latest.json`, ~0,9 MB): chiavi
  `Observation Time`, `Forecast Time`, `Data Format`, `coordinates`.
  `coordinates` è un array di terne `[longitudine, latitudine, aurora]`; la
  longitudine è il ciclo esterno (da 0, passo 1), la latitudine l'interno (da
  -90 a 90, passo 1). Valori interi osservati 0–26. **Ipotesi**: longitudine
  0–359 (quindi 360×181 punti), valore = probabilità di aurora in percento.
  Da verificare sul file intero e sul campo `Data Format`. La forma 360×181
  coincide con la copia del 2024 dentro `nws-aurora` (vedi "Librerie
  esistenti").
- **D-RAP** (`/text/drap_global_frequencies.txt`): commenti `#` con
  `Product Valid At`, `Estimated Recovery Time`, `X-RAY Message`,
  `Proton Message`; poi una griglia di frequenze (MHz, un decimale): righe di
  latitudine da 89 a -89 passo 2, ognuna con l'etichetta seguita da `|`;
  colonne di longitudine da -178 a 178 passo 4, con una riga di intestazione
  e una tratteggiata. Descrizione ricavata da un riassunto: **ipotesi** fino
  alla fixture.
- Per il GeoTIFF: le coordinate sono centri di cella su griglia regolare
  lat/lon (EPSG:4326). La longitudine di OVATION (0–359) va ruotata a
  -180…180 per l'uso su mappa: l'export lo fa, il modello conserva i dati
  come arrivano.

## Cambiamenti noti (SCN)

- **SCN 26-21** (2026-03-02): nuovi formati JSON dal 2026-03-31 circa, vecchi
  deprecati dal 2026-04-30.
- **Vento solare** (2026-06-30): fine di DSCOVR, SOLAR-1 primario, ACE di
  riserva; IMAP in arrivo.
- **SCN 26-39**: chiusura di GeoAlert (`geoalert.txt`) prevista il 2026-05-19,
  ma il file era ancora presente il 2026-10-15. Fuori dalla prima versione.
- **SCN 26-35**: chiusura del modello TEC CTIPe, sostituito da GloTEC.
- Le pagine di contenuto di `swpc.noaa.gov` rimandano a `www.spaceweather.gov`;
  `services.swpc.noaa.gov` risponde ancora. Avvisi e archivio:
  `https://www.weather.gov/notification/` e `services.swpc.noaa.gov/text/scn/`.

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
  "Avvisi" sotto.
- `nws-aurora` contiene una griglia OVATION del 2024-09-18 già convertita:
  65 160 punti, longitudine 0–359 (360 valori), latitudine -90…90 (181
  valori). Conferma indiretta dell'ipotesi della griglia 360×181.
