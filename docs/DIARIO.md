# Diario

## Da dove ripartire

Riscritto da capo a ogni fine sessione, mai accodato.

- **Stato**: tutte le tappe fino alla T18 fatte, più la T12; **0.3.0
  pubblicata su PyPI** il 2026-10-26 (tag `v0.3.0`, release su GitHub). Le
  voci nuove del CHANGELOG stanno in Unreleased.
- **Prossimo passo**: T17, il trasporto educato su politefetch, quando
  politefetch è su PyPI. La sua API è cambiata prima della pubblicazione
  (client con retry propri rifiutato, `NoPolicy`, `Transport.send` con un
  context manager): rileggerla, e decidere con quella sessione la
  semantica del 429 e il client HTTP.
- **Decisioni in sospeso**: il job `windows` fra i controlli richiesti di
  `main`, dopo il primo giro verde (lo aggiunge il maintainer, D-022). Il
  job `lowest` resta fuori dai richiesti (maintainer, 2026-10-26): per chi
  usa la libreria il solo minimo è httpx2 2.13, e il job lo prova lo stesso
  su ogni PR.
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
- **T5** (bollettini):
  - `parse/_text.py` è il kit dei prodotti testuali: `open_text_product`
    controlla `:Product:`/`:Issued:` e salta i `#`; `TextReader` solleva
    `SourceNotReady` se il testo finisce prima di un elemento (o dentro
    l'ultima riga senza a capo), altrimenti `ParseError` con `line`/`field`.
  - Giorni senza anno: anno più vicino all'`:Issued:` (`nearest_date`).
  - Tabelle dei Kp: celle con due decimali (più rigido delle frasi), scala
    opzionale `(G1)`–`(G5)` in `KpPeriod.noaa_scale`; 24 `KpPeriod` in
    ordine di tempo. Il 27-day outlook vuole esattamente 27 righe.
  - Un taglio dentro l'ultimo rationale del 3-day forecast non si rileva.
  - Il parser dei tempi `2026 Oct 13 2058 UTC` c'è anche in T4: da unire
    in `_common.py` (T8).
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
- **T7** (client):
  - `swpc_kit.client`: `Client` e `AsyncClient`, un metodo per prodotto
    (stessi nomi dei parser senza `parse_`, `27_day_outlook` →
    `twenty_seven_day_outlook`) più `fetch(product)`; `PRODUCTS` elenca i
    16 prodotti (URL e parser).
  - httpx2 sta solo in `client/_httpx.py`; il resto usa il protocollo
    `Transport` (`get(url, headers=, timeout=)`, `close()`). I test usano
    un trasporto finto, e `httpx2.MockTransport` per l'adattatore.
  - Redirect mai seguiti (`UnexpectedContent`); `408`/`425`/`429`/`5xx`,
    timeout e rete → `SourceNotReady`; altri stati e HTML →
    `UnexpectedContent`. `304` riusa il modello in memoria; `max_age` si
    misura su `data_time` anche dopo un `304`.
- **T8** (rifinitura):
  - `swpc_kit.models` riesporta tutti i modelli; `swpc_kit.export`
    riesporta `to_geojson` (non `write_geotiff`, per non importare numpy).
    `tests/test_public_api.py` controlla che ogni nome pubblico sia
    riesportato e abbia la docstring.
  - Gli esempi del README girano in `tests/test_readme.py`: blocchi
    `pycon` come doctest, blocchi `python` eseguiti con il client che legge
    le fixture al posto di SWPC. Un esempio nuovo va scritto lì.
  - `models/_checks.py` raccoglie `check_utc` e `check_values`.
- **T9** (skill):
  - `src/swpc_kit/skill/swpc-kit/`: `SKILL.md` a mano, `references/api.md`
    generato da `tools/build_skill.py` (introspezione: prodotti da
    `PRODUCTS` e dai `source_url` dei parser, campi dalle dataclass,
    significati dalla sezione `Attributes:` delle docstring). Chi cambia
    l'API rigenera; `--check` dice se è vecchio.
  - `python -m swpc_kit.skill`: `install` (predefinito
    `.claude/skills/swpc-kit/`; sostituisce solo una copia della stessa
    skill, altrimenti serve `--force`), `check`, `show`, `path`.
  - `tests/test_skill.py`: formato del frontmatter, versione = pacchetto,
    tabella = `PRODUCTS`, nomi citati esistenti, esempi eseguiti con il
    client sulle fixture (orologio fissato al 2026-10-15), comandi.
  - La fixture `swpc_from_fixtures` (client che legge le fixture) ora sta
    in `tests/conftest.py`, usata da README e skill.
- **T10** (schema comune delle skill): schema v1 con `sync` ed entry point
  `agent_skills`, superato in T11 (`docs/DECISIONI.md`, D-008 e D-010).
- **T11** (skill v2):
  - Tre file sono copie del modello comune delle skill di libreria, e si
    cambiano solo le costanti sopra la riga `nothing below this line`:
    `swpc_kit/skill/__init__.py` (`DISTRIBUTION`, `SKILL_NAME`; il resto è
    controllato per impronta, `SCHEMA_FINGERPRINT`), `tests/test_skill.py`
    (`PACKAGE`, `MIN_EXAMPLES`, `NOT_API`) e `tools/build_skill.py`
    (`MODULES`, `EXTRA`). Una correzione si fa nel modello e si ricopia.
  - `tests/test_skill_domain.py` ha i test di questa libreria. I blocchi
    `python nocheck` della SKILL.md li salta il test comune, ma li esegue
    sulle fixture il test di dominio.
  - Un modulo pubblico senza `__all__` esporta le classi e le funzioni
    pubbliche che definisce (`exports()` del generatore); il test del
    modello calcola gli stessi nomi da sé.
  - `CATALOGUE` di `codes.py` resta fuori da `__all__`: la sua `repr`
    riempirebbe il riferimento.
  - Il test della wheel salta in locale e in CI è obbligatorio:
    `ci.yml` costruisce la wheel e passa `SKILL_WHEEL=dist/*.whl`.
  - Misure: 85 nomi pubblici, tutti in `api.md` (verificato da test); 15
    citati nella SKILL.md, tutti verificati dai test dei nomi. SKILL.md 203
    righe, circa 2.400 token per attivazione; `api.md` 1008 righe, circa
    12.500 token, letto solo per sezione.
- **T13** (niente silenzi):
  - `parse/indices.py`: `_in_time_order` ordina e rifiuta i tempi ripetuti
    (D-011). RTSW e GOES ordinavano già; i tempi ripetuti lì sono normali
    (più sorgenti, più satelliti).
  - `data_time` del vento solare = ultimo record attivo (D-012).
  - `Record.missing()`: campo assente dal primo record →
    `UnexpectedContent`, da un record successivo → `ParseError` (D-013).
    `_ScalesRecord` lo ridefinisce (sempre `ParseError`).
  - `load_json`: un taglio dentro un letterale o un numero è
    `SourceNotReady` (`_cut_inside_a_token`); provato su 221.496 tagli di
    sei fixture, tutti `SourceNotReady`.
  - Client: `urls=` (D-014), `UnexpectedContent.status`/`.location`,
    `SwpcError.product`/`.url` messi da `BaseClient.locate()` in `fetch`.
    httpx2 caricata solo per il trasporto predefinito (`__getattr__` del
    modulo per `HttpxTransport`/`AsyncHttpxTransport`): la fixture
    `swpc_from_fixtures` sostituisce i trasporti in
    `swpc_kit.client._httpx`, non più in `swpc_kit.client`.
- **T14** (tolleranza):
  - `parse/_common.py`: `read_records(records, build)` costruisce un valore
    per record e mette gli altri in `SkippedRecord`; `MissingField` è il
    `ParseError` di un campo assente, e se lo stesso campo manca da tutti i
    record `read_records` dà `UnexpectedContent` (D-015, supera D-013).
  - Indici: `_series()` in `parse/indices.py` (tolleranza, tempi ripetuti in
    `skipped`, ordine). Vento solare, GOES, avvisi: `read_records`.
  - Limiti in `docs/FONTI.md`, "Plausibility limits" (D-017); le costanti
    stanno in testa ai parser.
  - `get_optional_int` / `get_optional_bool` con `may_be_absent=True` per i
    flag non documentati di RTSW.
  - Logger `swpc_kit.client` in `client/_core.py` (`_log_skipped`, debug sui
    `304`); i parser non scrivono log.
- **T15** (integrazione):
  - `swpc_kit/export/data.py`: `to_dict` e `to_records` (D-018). Le righe
    di un prodotto vengono da `values`, o dall'attributo in `_ROWS` (avvisi,
    scale, bollettini); i modelli annidati diventano colonne con prefisso,
    letti dalle annotazioni dei tipi, così una colonna c'è anche quando il
    modello annidato è `None`.
  - `Grid.value_near` e `_holding` in `models/grids.py`: prima il bordo
    verso nord o est su tutte le convenzioni di longitudine, poi l'altro.
  - `BaseClient.handle` è diviso in `reuse` (stato, `304`, HTML) e
    `remember` (log e cache): l'async fa il parse fra i due, in
    `asyncio.to_thread`. Gli argomenti dei client li controlla
    `_check_arguments`; il trasporto `check_transport`.
- **T16** (rilascio):
  - Job `lowest` in `.github/workflows/ci.yml` (D-020). In locale si prova
    con `UV_PROJECT_ENVIRONMENT=<cartella a parte>` e `uv sync --all-extras
    --resolution lowest-direct --python 3.12`. Attenzione: `uv sync
    --resolution` riscrive `uv.lock`, che poi va ripristinato.
  - Il README ha `### Trying again`, il ciclo di retry promesso da D-016.
- **T18** (GeoTIFF):
  - `swpc_kit/export/_tiff.py` è il contenitore TIFF; i numeri dei tag
    GeoTIFF e GDAL sono commentati in `geotiff.py`. rasterio serve solo ai
    test, per rileggere.
- **T12** (Windows e debiti):
  - Su Windows la suite intera è verde, anche in locale (D-022). La
    barriera di `tests/conftest.py` lascia aperto solo `connect` verso
    l'indirizzo locale; un test lungo con id costruiti dai dati deve dare
    id corti (`ids=`), perché pytest mette l'id in una variabile
    d'ambiente.
  - `MONTHS` e `text_time` stanno in `parse/_common.py`; i pattern e le
    maiuscole del mese restano di ciascun formato.
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
- 2026-10-16 — T5 (sub-agente, branch `-t5`): 3-day forecast, geomagnetic
  forecast e 27-day outlook con lettore comune dell'intestazione.
- 2026-10-16 — T6 (sub-agente, branch `-t6`): griglie OVATION e D-RAP,
  export GeoJSON e GeoTIFF, extra `geo` con numpy e rasterio.
- 2026-10-16 — T7: client sincrono e asincrono su httpx2 (scelto dopo aver
  verificato su PyPI lo stato di httpx), richieste condizionali, `max_age`;
  prova dal vivo su tutti i 16 prodotti. Resta: T8.
- 2026-10-17 — T8: API pubblica riesportata e verificata da test, README con
  esempi eseguiti dai test, CHANGELOG, versione 0.1.0, controlli comuni dei
  modelli raccolti. Nessuna tappa aperta.
- 2026-10-17 — T9: skill per gli assistenti AI nel pacchetto (guida a mano,
  riferimento API generato, comando `python -m swpc_kit.skill`), test che la
  tengono allineata al codice, versione 0.2.0. Nessuna tappa aperta.
- 2026-10-18 — T10: skill allineata allo schema comune dei pacchetti (entry
  point `agent_skills`, `sync` per l'hook `SessionStart`, marcatore), README
  con l'hook. Sempre 0.2.0. Nessuna tappa aperta.
- 2026-10-25 — preparazione all'open source, in locale: licenza MIT e autore
  Sidereus Team, `AGENTS.md`, `SPEC.md` e `docs/FONTI.md` in inglese, storia
  riscritta senza identità personali (i numeri di PR fino a qui sono quelli
  di `swpc-kit-archivio`, privato). Workflow di rilascio su PyPI e sdist con
  elenco esplicito di file. Resta: renderlo pubblico, la skill v2, la prima
  pubblicazione.
- 2026-10-25 — T11: skill sullo standard comune (modulo, test e generatore
  dal modello, dopo la correzione di sei suoi difetti trovati qui), via
  `sync` ed entry point; test della wheel in CI; `docs/DECISIONI.md`
  (D-001–D-010); T12 coi rinvii. Prova dei difetti iniettati: 26 su 26 presi
  (21 nella skill, 5 nel codice).
  Resta: prima pubblicazione, T12.
- 2026-10-25 — Revisione scettica prima della pubblicazione (agente nuovo,
  circa 70 varianti delle fixture): tappe T13–T16. T13: indici ordinati e
  senza duplicati, freschezza del vento solare sulla sorgente attiva, campo
  assente dal formato = `UnexpectedContent`, troncature dentro un token,
  `urls=`, errori del client con prodotto e URL, httpx2 caricata solo quando
  serve (D-011–D-014). Test visti rossi prima di ogni correzione: 49. Resta:
  T14 (decisione del maintainer), T15, T16, T12.
- 2026-10-25 — T14: tolleranza per record (decisione del maintainer, D-015),
  limiti di plausibilità (D-017), coerenza del Kp a 1 minuto, scala G nei
  bollettini, logger del client. Roadmap fino alla 0.3.0 e T17 su
  politefetch (D-016). Test visti rossi prima del codice: 67; difetti
  iniettati nella logica nuova: 9 su 9 presi. Resta: T15, T16, T12, poi
  0.3.0.
- 2026-10-25 — T15: `to_dict`/`to_records` in `swpc_kit.export`,
  `Grid.value_near` (la cella che contiene il punto, `None` fuori), parse
  async in un thread, argomenti dei client controllati, timeout per fase
  documentato (D-018). Test visti rossi prima del codice; difetti iniettati
  nella logica nuova: 18 su 18 presi. Resta: T16, T12, poi 0.3.0.
- 2026-10-25 — T16: README con installazione da PyPI, peso e piattaforme
  dell'extra `geo`, ciclo di retry; esempio di `SPEC.md` corretto;
  classifier "4 - Beta"; job `lowest` nella CI (D-020), che ha trovato due
  attriti con rasterio 1.4.0. Writer GeoTIFF senza rasterio valutato con un
  prototipo: fattibile, tappa T18 (D-019). Resta: T12, T18, 0.3.0.
- 2026-10-26 — T18: `write_geotiff` con la sola libreria standard
  (`export/_tiff.py` per il contenitore TIFF), extra `geo` tolto, numpy e
  rasterio solo nei test (D-021). Stesse 16 proprietà del file di rasterio,
  20 difetti iniettati su 20 presi. Resta: T12, 0.3.0.
- 2026-10-26 — Preparata la 0.3.0: commit di versione con la sezione del
  CHANGELOG che presenta il pacchetto, i link in fondo e il tag `v0.3.0`.
  Note della release provate con lo stesso `awk` del workflow. Il nome
  `swpc-kit` su PyPI era ancora libero.
- 2026-10-26 — 0.3.0 pubblicata. T12: Windows supportato, con la suite
  verde e un job `windows` nella CI (barriera aperta solo verso l'indirizzo
  locale, id corti, fixture copiate invece del symlink); tabella dei mesi e
  `text_time` in `_common.py`; override di mypy per rasterio tenuto
  (D-022). Resta: T17.
