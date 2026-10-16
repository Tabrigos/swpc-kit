# Diario

## Da dove ripartire

Riscritto da capo a ogni fine sessione, mai accodato.

- **Stato**: T0, T1 e T2 fatte. Parser e modelli degli indici (Kp 3 ore,
  previsione, Kp 1 minuto, Dst, F10.7, scale NOAA), formati vecchi e nuovi.
- **Prossimo passo**: T3–T6, in parallelo (sub-agenti, un branch e una PR
  per tappa); poi T7.
- **Da sapere** (per chi scrive i prossimi parser):
  - `swpc_kit/parse/_common.py` è il kit comune: `load_json` classifica gli
    errori (vuoto o troncato → `SourceNotReady`; HTML o non JSON →
    `UnexpectedContent`), `json_records` legge sia l'array di oggetti sia
    l'array di array con intestazione e dà dei `Record`, i cui metodi
    `get_time`/`get_float`/`get_int`/`get_str` (anche `get_optional_*`)
    convertono, controllano gli intervalli e sollevano `ParseError` con campo
    e indice. `parse_time` accetta `T` o spazio, `.000`, `Z`; senza fuso è
    UTC. Il BOM iniziale è tollerato.
  - Schema dei modelli: `@dataclass(frozen=True, slots=True)`, `values` come
    tupla non vuota, `source_url`, `data_time` come proprietà; i tempi sono
    controllati UTC in `__post_init__`. I parser hanno `source_url=` con
    l'URL canonico come valore predefinito (costanti `*_URL` in
    `parse/indices.py`, utili al client in T7).
  - `parse/__init__.py` riesporta i parser (riga d'esempio di `SPEC.md`):
    ogni tappa aggiunge i suoi, toccando solo quelle righe.
  - `data_time`: previsione del Kp = ultima voce `observed`; scale NOAA =
    voce più recente con chiave ≤ 0.
  - Fixture: `tests/fixtures/<prodotto>/` (vedi il suo README); OVATION
    ridotta non è una griglia completa; RTSW decrescente con minuti senza
    record attivo e IMAP fuori minuto; avvisi con `\r\n` e `\n` mescolati.
  - `ParseError(message, field=, line=, index=)`; ruff con `D` e `DTZ`; i test
    non aprono socket.
- **T3** (vento solare e GOES):
  - RTSW: i modelli tengono tutte le fonti in ordine crescente;
    `active_series()`/`active_at()` scelgono `active: true` senza ripiegare
    su un'altra fonte (istanti di solo ACE o IMAP restano senza record
    attivo). `data_time` = ultimo `time_tag` di qualunque fonte; la
    freschezza della fonte attiva è `latest_active().time` (utile a T7).
  - `Record` ha anche `get_optional_float`, `get_bool`, `get_optional_bool`.
  - `FlareClass.from_flux` (banda 0.1-0.8 nm, moltiplicatore troncato a un
    decimale). I parser GOES valgono per 6-hour/3-day/7-day e `secondary/`
    con `source_url=`, ma quei file non sono verificati.
  - `_check_utc`/`_check_values` sono duplicati nei moduli dei modelli: da
    raccogliere in T8.
- **T4** (avvisi):
  - `parse_alerts` → `Alerts` di `AlertMessage`. Intestazione (codice,
    serial, `Issue Time`) obbligatoria: un errore lì è `ParseError` con
    `field="message.<etichetta>"` e l'indice. Gli altri campi sono tipizzati
    quando la forma è nota, altrimenti `None`; il grezzo resta in `fields`.
  - `issued` = `issue_datetime` (ms), `issue_time` = riga del testo (minuto).
    Il serial non è univoco (gli `ALTEF3` continuati lo ripetono).
  - Array vuoto = nessun avviso: `Alerts` vuoto con `data_time` `None`
    (T7 deve gestirlo con `max_age`).
  - `swpc_kit/codes.py` copre i 39 codici della tabella ufficiale (riletta
    il 2026-10-16); restano dedotti solo i codici corti `K08A`, `K09A`,
    `A50F`, `A99F`.
  - Il parser dei tempi `2026 Oct 13 2058 UTC` è privato in
    `parse/alerts.py`: se T5 ne ha uno uguale, unirli in `_common.py` (T8).
- **T6** (griglie ed export):
  - `models/grids.py`: `Grid` comune (latitudini da sud a nord, longitudini
    come arrivano, `wrapped()` per -180…180); gli export accettano un
    `GridProduct` (`grid`, `source_url`, `data_time`, `times`).
  - OVATION rigoroso per default (360×181); la fixture ridotta si legge con
    `parse_ovation_aurora(raw, partial=True)`.
  - D-RAP: tabella fermata prima del polo o ultima riga corta senza `\n` →
    `SourceNotReady`; riga sbagliata in mezzo → `ParseError` con `line`.
  - `export.geojson.to_geojson(product, threshold=, geometry=)` (soglia ≥,
    poligoni o punti); `export.geotiff.write_geotiff` (extra `geo`: numpy,
    rasterio; float32, EPSG:4326, tempi nei tag). Override mypy per
    rasterio; in alternativa gli stub `types-rasterio`.
  - D-RAP: il valore è la Highest Affected Frequency (1 dB), verificato
    sulla documentazione SWPC. Restano ipotesi l'unità % di OVATION e il
    formato di `Estimated Recovery Time` quando c'è una stima.
- **Dubbi aperti**: le ipotesi rimaste in `docs/FONTI.md` (UTC dei
  `time_tag` senza `Z`, millisecondi del vecchio Dst e flusso, significato
  delle chiavi di `noaa-scales.json`, unità dei valori OVATION).

## Log

Una riga per sessione: data, tappa, cosa è entrato, cosa resta.

- 2026-10-15 — progetto avviato: `SPEC.md`, `docs/FONTI.md` (ricognizione dei
  prodotti SWPC e delle librerie esistenti), `docs/TAPPE.md`.
- 2026-10-15 — T0: impianto, errori, CI, README. Ricognizione di `swpclib` e
  `nws-aurora` (nessuna copre la specifica; nome `swpc-kit` libero su PyPI).
  Resta: T1.
- 2026-10-15 — T1 (nella stessa sessione di T0, su richiesta): strumento di
  registrazione e di costruzione del vecchio formato, fixture di 16 prodotti,
  3 esempi ufficiali, 3 file costruiti; ipotesi di `FONTI.md` verificate.
  Resta: T2–T6.
- 2026-10-15 — T2 (stessa sessione, su richiesta): `parse/_common.py`,
  modelli e parser degli indici, 215 test. Resta: T3–T6.
- 2026-10-16 — T3 (sub-agente, branch `-t3`): RTSW mag e plasma con scelta
  della fonte attiva, GOES X con classe del brillamento e protoni per soglia.
- 2026-10-16 — T4 (sub-agente, branch `-t4`): `parse_alerts`, modelli dei
  messaggi, catalogo dei codici con voci verificate e dedotte.
- 2026-10-16 — T6 (sub-agente, branch `-t6`): griglie OVATION e D-RAP,
  export GeoJSON e GeoTIFF, extra `geo` con numpy e rasterio.
