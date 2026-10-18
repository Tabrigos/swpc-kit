# Diario

## Da dove ripartire

Riscritto da capo a ogni fine sessione, mai accodato.

- **Stato**: T0–T10 fatte: versione **0.2.0**, non pubblicata su PyPI.
  Parser e modelli per tutti i prodotti della prima versione, export GeoJSON
  e GeoTIFF, client sincrono e asincrono, README con esempi verificati da
  `tests/test_readme.py`, `CHANGELOG.md`, skill per gli assistenti AI
  dentro il pacchetto, sincronizzata nei progetti da `sync`.
- **Prossimo passo**: nessuna tappa aperta. Da decidere: pubblicazione su
  PyPI (nome `swpc-kit` libero al 2026-10-15, da ricontrollare), licenza
  (`SPEC.md`: "da decidere quando il repo diventa pubblico"), tag `v0.2.0`.
- **Decisioni in sospeso**: override mypy per rasterio o stub
  `types-rasterio` (T6); `alerts.json` vuoto = elenco vuoto con
  `data_time` `None` (T4; il client non lo considera mai vecchio); unire il
  parser dei tempi testuali di T4 (`parse/alerts.py`) e T5 (`parse/_text.py`).
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
- **T10** (schema comune delle skill):
  - Schema "skill dei pacchetti" v1, concordato con la sessione di
    politefetch: entry point `agent_skills`, `sync`, marcatore
    `.package-skill`, `.gitignore` `*` solo nelle copie create da `sync`.
    Il modulo `swpc_kit/skill/__init__.py` deve restare uguale a quello di
    politefetch salvo le costanti: un cambiamento va concordato.
  - `sync` legge la versione da `metadata.version` di `SKILL.md` (copia e
    pacchetto); aggiorna anche se una delle due manca. Riepilogo:
    `skills: a 1.0 (added), b 2.0 (updated), c 0.2.0, d (removed)` o
    `skills: none`.
  - Non c'è un file DECISIONI: la scelta sta in `SPEC.md` (Architettura).
  - La rimozione confronta i marcatori con gli entry point **dichiarati**
    (`declared()`), non con quelli caricati: un pacchetto installato ma
    rotto tiene la sua copia vecchia e dà un avviso.
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
