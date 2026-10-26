# Decisioni

Le scelte di progetto con il loro perché. Una voce per decisione, numerata,
mai riscritta: se una scelta cambia, si aggiunge una voce nuova che rimanda
alla vecchia e la vecchia prende la riga "Superata da".

Le voci da D-001 a D-009 sono state scritte in T11 (2026-10-25) raccogliendo
scelte già prese e sparse fra `SPEC.md`, `docs/FONTI.md` e il diario; la data
è quella della scelta, non della scrittura.

## Formato

```
## D-NNN — Titolo breve

- **Data e tappa**: AAAA-MM-GG, Tn
- **Contesto**: il problema, in poche righe.
- **Decisione**: cosa si fa.
- **Alternative scartate**: cosa e perché no.
- **Conseguenze**: cosa cambia per le tappe successive.
```

---

## D-001 — Il nucleo usa solo la libreria standard

- **Data e tappa**: 2026-10-15, T0
- **Contesto**: chi deve solo leggere un file di SWPC già scaricato non deve
  installare un client HTTP né GDAL.
- **Decisione**: parser, modelli ed export GeoJSON usano solo la libreria
  standard. Le dipendenze stanno negli extra: `client` (HTTP) e `geo`
  (numpy, rasterio). Una dipendenza nuova si giustifica nella PR.
- **Alternative scartate**: pydantic per i modelli (dipendenza nel nucleo per
  una validazione che le dataclass con `__post_init__` già fanno).
- **Conseguenze**: un modulo che importa un extra fallisce all'import con un
  messaggio che dice quale extra installare; i test della skill girano con
  tutti gli extra.

## D-002 — La freschezza si misura sul tempo dichiarato dal contenuto

- **Data e tappa**: 2026-10-15, `SPEC.md` (applicata in T7)
- **Contesto**: un `304 Not Modified` o un `Last-Modified` recente non dicono
  che il dato è nuovo: SWPC riscrive i file anche senza dati nuovi.
- **Decisione**: ogni modello espone `data_time`, il tempo più recente che il
  contenuto dichiara; `max_age` del client si misura su quello, anche dopo un
  `304`, e solleva `StaleData`.
- **Alternative scartate**: l'età dagli header HTTP (misura il file, non il
  dato).
- **Conseguenze**: per ogni prodotto va deciso quale tempo è `data_time` (per
  la previsione del Kp l'ultimo valore osservato, per i bollettini l'ora di
  emissione).

## D-003 — `alerts.json` vuoto è un elenco vuoto, non un errore

- **Data e tappa**: 2026-10-16, T4
- **Contesto**: nei periodi calmi `alerts.json` può essere un array vuoto.
  Non si confonde con un file troncato, che non è JSON valido.
- **Decisione**: array vuoto = `Alerts` senza messaggi e con `data_time`
  `None`; `max_age` non lo rifiuta mai.
- **Alternative scartate**: `SourceNotReady` (farebbe ritentare per sempre
  nei giorni senza avvisi); `data_time` uguale all'ora della richiesta
  (inventerebbe un tempo che il contenuto non dichiara).
- **Conseguenze**: chi chiama deve accettare `data_time` `None` per questo
  prodotto.

## D-004 — OVATION rigoroso per default

- **Data e tappa**: 2026-10-16, T6
- **Contesto**: la griglia OVATION completa è 360×181; un file a metà ha
  meno punti ma è ancora JSON valido.
- **Decisione**: `parse_ovation_aurora` vuole la griglia completa;
  `partial=True` accetta una griglia con longitudini intere mancanti (serve
  alla fixture ridotta).
- **Alternative scartate**: accettare sempre griglie parziali (una mappa con
  un buco sembrerebbe "nessuna aurora").
- **Conseguenze**: i test e gli esempi che usano la fixture ridotta passano
  `partial=True`.

## D-005 — Client HTTP su `httpx2`

- **Data e tappa**: 2026-10-16, T7
- **Contesto**: l'ultima versione stabile di `httpx` è la 0.28.1 del
  2024-12-06, poi solo versioni di sviluppo; `httpx2` (Pydantic) ne è la
  continuazione mantenuta, con la stessa API (verifica su PyPI in
  `docs/FONTI.md`, "HTTP client").
- **Decisione**: l'extra `client` usa `httpx2>=2.13`. Solo
  `swpc_kit/client/_httpx.py` la importa; i client dipendono dai protocolli
  `Transport` / `AsyncTransport`.
- **Alternative scartate**: `httpx` (fermo); `niquests` (attivo, API di
  requests); `aiohttp` (solo asincrono); `requests` (solo sincrono).
- **Conseguenze**: tornare a `httpx` o cambiare libreria tocca un modulo
  solo. Da allineare con politefetch, che usa `httpx`: aperta, fuori da T11.

## D-006 — Classificazione degli esiti HTTP

- **Data e tappa**: 2026-10-16, T7
- **Contesto**: chi chiama deve sapere se ritentare o fermarsi, senza leggere
  il testo dei messaggi.
- **Decisione**:
  - `408`, `425`, `429`, `5xx`, timeout, errore di rete, file troncato →
    `SourceNotReady` (ritentare più tardi);
  - redirect (mai seguiti), altri stati, pagina HTML, formato sconosciuto →
    `UnexpectedContent` (non ritentare in un ciclo);
  - `304` → il modello già in memoria, ancora controllato con `max_age`.
- **Alternative scartate**: seguire i redirect (SWPC li usa per le pagine di
  annuncio, che non sono il prodotto); un'unica eccezione con il codice di
  stato (sposta la classificazione su ogni chiamante).
- **Conseguenze**: il `429` dice "ritenta più tardi" ma non quando; politefetch
  invece congela l'host fino allo sblocco. Da allineare con politefetch:
  aperta, fuori da T11.

## D-007 — rasterio senza tipi: override di mypy

- **Data e tappa**: 2026-10-16, T6
- **Contesto**: rasterio non ha `py.typed`; con `mypy --strict` i suoi nomi
  non hanno tipo.
- **Decisione**: `ignore_missing_imports` per `rasterio` e `rasterio.*` in
  `pyproject.toml`; i nomi restano `Any`, usati solo in
  `export/geotiff.py` e nel suo test.
- **Alternative scartate**, per ora: gli stub `types-rasterio` (una
  dipendenza di sviluppo nuova).
- **Conseguenze**: provvisoria, da rivedere in T12.

## D-008 — Skill dei pacchetti, schema v1

- **Data e tappa**: 2026-10-18, T10
- **Superata da**: D-010
- **Contesto**: i pacchetti dello stesso autore (swpc-kit, politefetch)
  portano una skill e devono comportarsi allo stesso modo.
- **Decisione**: entry point `agent_skills`, `python -m <pkg>.skill sync` da
  un hook `SessionStart` che copia le skill di tutti i pacchetti installati,
  marcatore `.package-skill`, `.gitignore` con `*` nelle copie create da
  `sync`, confronto per versione.
- **Conseguenze**: modulo `skill` uguale nei due pacchetti salvo le costanti.

## D-009 — Pubblicazione: MIT, Sidereus Team, PyPI solo dalla CI

- **Data e tappa**: 2026-10-25, preparazione all'open source
- **Contesto**: il repository diventa pubblico e il pacchetto va su PyPI.
- **Decisione**: licenza MIT, autore Sidereus Team. Pubblicazione su PyPI
  solo da `.github/workflows/release.yml` con Trusted Publishing (nessun
  token), al tag `vX.Y.Z` e con l'approvazione del maintainer
  nell'environment `pypi`; l'avvio manuale pubblica su TestPyPI. Sdist con
  un elenco esplicito di file.
- **Alternative scartate**: pubblicare dal PC (token sulla macchina, e un
  file locale finirebbe nello sdist).
- **Conseguenze**: regole operative in `AGENTS.md`, "Releases". La prima
  versione pubblicata viene dopo T11.

## D-010 — Skill di libreria, schema 1 del modello comune

- **Data e tappa**: 2026-10-25, T11
- **Sostituisce**: D-008
- **Contesto**: lo schema v1 aveva quattro difetti: `sync` portava nel
  contesto dell'agente le istruzioni di qualunque pacchetto installato,
  dipendenze transitive comprese; le copie erano ignorate da git, quindi
  nessuno le rileggeva; il confronto per versione non vedeva le correzioni
  senza cambio di versione; `--force` cancellava qualunque cartella.
- **Decisione**:
  - `swpc_kit/skill/__init__.py` copiato dal modello comune (`path`, `show`,
    `check` per impronta, `install --target` solo in
    `.claude/skills/swpc-kit` o `.agents/skills/swpc-kit`, marcatore
    `.skill-libreria.json`); un test ne confronta l'impronta.
  - `tests/test_skill.py` e `tools/build_skill.py` dal modello, con le sole
    costanti di questo pacchetto; i test di dominio in
    `tests/test_skill_domain.py`.
- **Alternative scartate**: tenere il generatore su misura di T9. Il modello
  com'era il 25/10 mattina, provato su questo pacchetto, dava 168 righe
  contro 692: perdeva i modelli (stanno in sottomoduli senza `__all__`) e il
  significato dei campi (sezione `Attributes:` delle docstring), e storpiava
  gli URL. Segnalati sei difetti a chi tiene il modello, corretti lo stesso
  giorno. Il modello corretto dà 1008 righe con tutti i campi spiegati. Si
  perde la tabella "metodo, parser, URL" del vecchio riferimento: l'URL resta
  nel `source_url` predefinito di ogni parser, la tabella dei metodi nella
  SKILL.md.
- **Conseguenze**: via `sync`, l'entry point e `--force` prima della prima
  pubblicazione. Il progetto che usa swpc-kit tiene la copia in git e lancia
  `check` in CI. politefetch deve passare allo stesso modello.

## D-011 — Le serie degli indici sono ordinate e senza tempi ripetuti

- **Data e tappa**: 2026-10-25, T13
- **Superata in parte da**: D-015 (il tempo ripetuto va in `skipped`)
- **Contesto**: README e SKILL insegnano `values[-1]` come valore più recente,
  ma i parser degli indici tenevano l'ordine del file: un file in ordine
  inverso dava un valore vecchio senza errore. RTSW e GOES già ordinavano.
- **Decisione**: i parser di Kp, previsione del Kp, Kp a 1 minuto, Dst e
  F10.7 ordinano per tempo; un tempo ripetuto è `ParseError` con
  `field="time_tag"` e l'indice del secondo record.
- **Alternative scartate**: tenere il primo dei duplicati (nasconde un file
  incoerente); solo controllare l'ordine e sollevare (rifiuterebbe un file
  valido scritto in un altro ordine).
- **Conseguenze**: `values` è "dal più vecchio, un valore per tempo" per
  tutte le serie degli indici.

## D-012 — La freschezza del vento solare segue la sorgente attiva

- **Data e tappa**: 2026-10-25, T13
- **Contesto**: `data_time` delle serie RTSW era il record più recente di
  qualunque sorgente. Con SOLAR1 (attiva) ferma e ACE (riserva) che
  continua, `max_age` accettava come recente un Bz vecchio di ore.
- **Decisione**: `data_time` è il tempo dell'ultimo record attivo; senza
  record attivi, quello del record più vecchio (nessun tempo del file ha dati
  attivi).
- **Alternative scartate**: un `active_data_time` a parte, usato dal client
  (due tempi da spiegare, e chi controlla a mano `data_time` sbaglierebbe
  ancora); `data_time` `None` senza record attivi (`max_age` non lo
  rifiuterebbe mai, come gli avvisi vuoti).
- **Conseguenze**: per il vento solare `data_time` può essere più vecchio
  del record più recente del file.

## D-013 — Un campo assente dal primo record è un formato nuovo

- **Data e tappa**: 2026-10-25, T13
- **Superata da**: D-015 (la regola guarda tutti i record, non il primo)
- **Contesto**: i docstring dei parser promettono `UnexpectedContent` per
  "content is not this product", ma un campo rinominato o un prodotto
  sbagliato davano `ParseError`. Chi distingue "SWPC ha cambiato formato"
  (aggiornare la libreria) da "un valore è incoerente" li confondeva.
- **Decisione**: un campo che manca dal primo record di un prodotto JSON è
  `UnexpectedContent`; se manca da un record successivo, il formato è quello
  noto e il file è incoerente: `ParseError` con campo e indice. In
  `noaa-scales.json`, dove i gruppi non sono record di un elenco, resta
  `ParseError`.
- **Alternative scartate**: cambiare solo i docstring (lascia la confusione
  a chi chiama); controllare l'intestazione dei campi in `json_records`
  (ogni parser dovrebbe dichiarare i suoi campi).
- **Conseguenze**: un rinomina di SWPC dà `UnexpectedContent`, con il nome
  del campo nel messaggio.

## D-014 — Un prodotto spostato si raggiunge con `urls=`

- **Data e tappa**: 2026-10-25, T13
- **Contesto**: se SWPC sposta un file, il client dà `UnexpectedContent`
  (301 o 404) e non segue i redirect (D-006). Rimediare voleva
  `dataclasses.replace` su un `Product`, non documentato.
- **Decisione**: `Client(urls={nome: url})` e lo stesso per `AsyncClient`;
  una chiave che non è un prodotto è `ValueError`. `UnexpectedContent` porta
  `status` e `location`; ogni errore che passa dal client porta `product` e
  `url`, anche nel messaggio.
- **Alternative scartate**: seguire i redirect (D-006); un `url=` per ogni
  chiamata (andrebbe ripetuto in ogni punto del programma).
- **Conseguenze**: il nuovo indirizzo si mette in un solo posto finché una
  versione nuova non lo conosce.

## D-015 — Tolleranza per record nei prodotti JSON fatti di record

- **Data e tappa**: 2026-10-25, T14 (scelta del maintainer)
- **Sostituisce**: D-013; in parte D-011
- **Contesto**: un solo record sbagliato faceva fallire l'intero prodotto, e
  il record resta nel file per tutta la sua finestra (24 h il vento solare,
  7 giorni il Kp, circa 30 giorni gli avvisi): il prodotto restava illeggibile
  altrettanto. Prima della prima versione pubblica il cambio di contratto non
  rompe nessuno.
- **Decisione**:
  - indici, vento solare, GOES e avvisi si leggono record per record
    (`read_records`): un record che non si legge va in `skipped` del modello
    (`SkippedRecord`: indice, campo, motivo), gli altri si leggono;
  - il prodotto fallisce solo se nessun record si legge: con
    `UnexpectedContent` se lo stesso campo manca da tutti (formato nuovo),
    altrimenti con il `ParseError` del primo record;
  - un tempo ripetuto in una serie degli indici: il secondo record va in
    `skipped`;
  - i flag non documentati di RTSW possono mancare: diventano `None`;
  - bollettini, griglie e `noaa-scales.json` restano rigidi: sono tabelle,
    una riga sbagliata rende dubbio il resto;
  - il client scrive un warning sul logger `swpc_kit.client` per ogni
    prodotto con record scartati; i parser restano senza effetti.
- **Alternative scartate**: tolleranza a scelta con `strict=False` (due modi
  di funzionare da documentare e provare); "tutto o niente" dichiarato (chi
  lo usa in produzione resta senza dati per giorni).
- **Conseguenze**: chi chiama guarda `skipped` quando conta la completezza;
  `values` può avere buchi dove un record è stato scartato.

## D-016 — Trasporto educato su politefetch, dopo la 0.3.0

- **Data e tappa**: 2026-10-25, scelta del maintainer dopo la risposta
  dell'agente di politefetch
- **Contesto**: in un cron il client non regge: nessun retry, `Retry-After`
  ignorato, cache dell'ETag solo in memoria. politefetch esiste per questo,
  ma non è ancora su PyPI.
- **Decisione**: un extra `swpc-kit[polite]` con un `PoliteTransport` che
  avvolge il `Transport` di swpc-kit dentro `gate.attempt(url)` del core di
  politefetch; httpx2 resta il client di swpc-kit; intervallo minimo per
  host (scelta del maintainer, valida anche in politefetch); un errore
  distinto per l'host congelato e per i rifiuti con `retry_after`. Esce dopo
  la 0.3.0 di swpc-kit, in T17.
- **Alternative scartate**: usare il client di politefetch (`HttpxFetcher`,
  non httpx2, e con i suoi controlli sul contenuto); far uscire swpc-kit
  dopo politefetch (nessuno dei due deve aspettare l'altro).
- **Conseguenze**: la 0.3.0 documenta un ciclo di retry nel README.

## D-017 — Limiti di plausibilità larghi, senza sentinelle

- **Data e tappa**: 2026-10-25, T14
- **Contesto**: Dst 99999, Bz -99999 o un flusso X di 1 W/m² passavano senza
  errore. SWPC non documenta valori sentinella per i campi fisici.
- **Decisione**: limiti molto più larghi di qualunque misura (tabella in
  `docs/FONTI.md`, "Plausibility limits"); oltre il limite il record va in
  `skipped`. Nessun valore diventa `None` per un limite. In più: coerenza
  del Kp a 1 minuto (verificata su 358 record) e numeri fra virgolette solo
  decimali (niente `_`, `+`, `nan`, `inf`).
- **Alternative scartate**: trattare `-99999` come sentinella e renderlo
  `None` (senza fonte è un'ipotesi); limiti stretti sui valori tipici
  (scarterebbero proprio le tempeste che interessano).
- **Conseguenze**: un cambio di unità o una sentinella nuova si vedono in
  `skipped` invece che nei dati.

## D-018 — Dati semplici con funzioni, griglie per cella, timeout per fase

- **Data e tappa**: 2026-10-25, T15
- **Contesto**: la revisione scettica ha trovato tre attriti d'integrazione:
  - nessun modo di passare un modello a JSON o a pandas;
  - `value_at` vuole il centro esatto della cella e solleva `KeyError`;
  - il `timeout` non dice a cosa si applica.
- **Decisione**:
  - `to_dict` e `to_records` sono funzioni di `swpc_kit.export`, non
    metodi: una sola implementazione per tutti i modelli, e i modelli non
    cambiano. Danno solo i campi: le proprietà (`data_time`,
    `flare_class`) restano sui modelli.
  - `to_records` tiene i tempi come `datetime` UTC (pandas li legge come
    `datetime64[ns, UTC]`); `to_dict` li scrive in ISO 8601 con `Z`.
  - `Grid.value_near` dà la cella che contiene il punto, o `None` fuori
    dalla griglia o in un buco di una griglia ridotta, non la cella più
    vicina a ogni costo: un punto in un buco avrebbe il valore di una cella
    lontana. Sul bordo vince la cella a nord o a est; i bordi esterni sono
    delle celle esterne.
  - Il timeout resta quello di httpx2, per fase, e lo dicono le docstring;
    per un limite sull'intera chiamata si usa `asyncio.timeout()`.
- **Alternative scartate**:
  - metodi `to_dict()` su ogni modello (sedici copie della stessa cosa);
  - `value_near` che cerca sempre la cella più vicina;
  - una scadenza totale nel client (nel client sincrono servirebbe un
    thread per richiesta).
- **Conseguenze**: `value_at` resta com'era, per chi ha il centro esatto.

## D-019 — Un writer GeoTIFF senza rasterio si può fare: tappa T18

- **Data e tappa**: 2026-10-25, T16 (solo valutazione)
- **Contesto**: l'extra `geo` pesa circa 140 MB (numpy e rasterio con GDAL
  dentro le ruote). Le ruote dell'ultima rasterio (1.5.2) vogliono macOS 15
  o glibc 2.28. Su un sistema più vecchio pip prova a compilare GDAL e
  fallisce, salvo `--only-binary rasterio`. Il raster da scrivere è piccolo:
  al massimo 360 per 181 celle, una banda.
- **Valutazione**: un prototipo fuori dal repo, di circa 120 righe con
  `struct` e `zlib`, scrive lo stesso file di oggi:
  - TIFF little-endian, float32, deflate;
  - tag GeoTIFF (scala, punto di aggancio, chiavi con EPSG:4326 e
    pixel-is-area);
  - tag di GDAL con i metadati e il nodata.

  Riletti con rasterio, i file di D-RAP e OVATION ridotta danno gli stessi
  CRS, trasformazione, valori, nodata, tag, descrizione e unità del file
  scritto con rasterio.
- **Scelta**: per ora resta rasterio. Il writer con la sola libreria
  standard è una tappa sua, T18, con rasterio solo nei test, che rileggono
  il file con GDAL. Il maintainer decide se viene prima o dopo la 0.3.0.
- **Alternative scartate**: tifffile (toglie GDAL ma non numpy, e i tag
  GeoTIFF vanno scritti a mano lo stesso); lasciare `geo` com'è senza
  documentarlo (il README ora dice peso e piattaforme).
- **Conseguenze**: se T18 arriva dopo la 0.3.0, l'extra `geo` resta, vuoto,
  perché chi lo scrive non trovi un errore.

## D-020 — "Beta", e le versioni minime provate dalla CI

- **Data e tappa**: 2026-10-25, T16
- **Contesto**: il classifier diceva "2 - Pre-Alpha". I minimi in
  `pyproject.toml` (`httpx2>=2.13`, `numpy>=2.0`, `rasterio>=1.4`) non li
  provava nessuno.
- **Decisione**:
  - "4 - Beta": la libreria fa ciò che dice `SPEC.md` ed è provata sui
    formati registrati, ma l'API può ancora cambiare prima della 1.0;
  - un job `lowest` nella CI (`UV_RESOLUTION=lowest-direct`, Python 3.12)
    fa girare i test con i minimi. La `PendingDeprecationWarning` di affine
    3 con rasterio prima della 1.5.2 si ignora solo lì: per chi usa la
    libreria è un avviso, non un errore.
- **Alternative scartate**: "3 - Alpha" (troppo prudente per un'API
  documentata e provata); alzare il minimo a rasterio 1.5.2 (toglierebbe le
  ruote per macOS prima della 15 e per glibc prima della 2.28).
- **Conseguenze**: un minimo che smette di funzionare si vede nella CI. Il
  job non è fra i controlli richiesti di `main` finché il maintainer non lo
  aggiunge.

## D-021 — GeoTIFF con la sola libreria standard, e niente extra `geo`

- **Data e tappa**: 2026-10-26, T18 (supera la scelta di D-019 di tenere
  rasterio)
- **Contesto**: il maintainer ha messo la T18 prima della 0.3.0, quindi
  l'extra `geo` non è mai uscito su PyPI.
- **Decisione**:
  - `write_geotiff` scrive il file con `struct` e `zlib`. Il contenitore
    TIFF sta in `swpc_kit/export/_tiff.py`, che non sa nulla di GeoTIFF.
    I tag GeoTIFF e GDAL li sceglie `geotiff.py`, nel modo in cui li scrive
    GDAL: strip da circa 8 KB, deflate, metadati in `GDAL_METADATA` (42112)
    e nodata in `GDAL_NODATA` (42113).
  - numpy e rasterio passano nel gruppo `dev`: i test rileggono i file con
    GDAL. Un test legge la directory del TIFF con `struct`, per le regole
    che GDAL perdona: tag in ordine crescente, scala positiva.
  - L'extra `geo` si toglie del tutto, scelta del maintainer: chi scrive
    `swpc-kit[geo]` riceve da pip un avviso, non un errore.
  - Un `nodata` che non sta in un `float32` è un `ValueError`; con numpy
    diventava `inf` con un avviso.
- **Alternative scartate**: lasciare `geo` vuoto (un extra che non fa
  niente, da spiegare per sempre); file di riferimento scritti con
  rasterio fra le fixture (le fixture sono contenuto SWPC, e i test
  controllano già ogni proprietà che rasterio rilegge).
- **Verifica**: prima di togliere il writer vecchio, uno script fuori dal
  repo ha fatto scrivere ai due writer D-RAP, OVATION ridotta e completa e
  due nodata diversi. Riletti con rasterio, i file nuovi danno le stesse 16
  proprietà dei vecchi, compresi i blocchi, e il confronto si è visto
  segnalare un nodata diverso. Venti difetti iniettati nel writer, tutti
  presi dai test.
- **Conseguenze**: per chi usa la libreria cambia solo l'installazione. I
  minimi di numpy e rasterio provati dal job `lowest` diventano quelli dei
  test.

## D-022 — Windows supportato; tempi testuali con una parte comune; niente stub di rasterio

- **Data e tappa**: 2026-10-26, T12 (scelte del maintainer)
- **Contesto**: su Windows la suite non passava tutta. Le cause stavano
  tutte nei test:
  - la barriera di rete bloccava la coppia di socket con cui l'event loop
    di asyncio si risveglia, che su Windows si connette a 127.0.0.1;
  - gli id di `test_drap_inconsistent_lines` contenevano un file D-RAP
    intero, oltre il limite di una variabile d'ambiente di Windows (pytest
    ci mette l'id);
  - `test_readme` creava un symlink, che su Windows richiede un privilegio.

  Gli avvisi lasciati dai test async cadevano poi su test innocenti.
- **Decisione**:
  - Windows è supportato. Un job `windows` nella CI fa girare la suite
    intera con la wheel. È un job a sé, non una voce della matrice di
    `checks`, così i nomi dei controlli richiesti di `main` non cambiano;
    il maintainer lo aggiunge fra i richiesti dopo il primo giro verde.
  - La barriera lascia aperto solo `connect` verso l'indirizzo locale
    (`127.0.0.1`, `::1`); `connect_ex`, `create_connection` e
    `getaddrinfo` restano chiusi. Un test lo prova.
  - Tempi testuali: la tabella dei mesi e la costruzione dell'ora UTC
    (`text_time`) stanno in `parse/_common.py`. Ogni formato tiene il suo
    pattern e il suo modo di leggere il mese: i bollettini lo leggono senza
    badare alle maiuscole, gli avvisi solo come `Oct`. Due test fissano
    questa differenza.
  - rasterio resta con l'override di mypy (`ignore_missing_imports`).
- **Alternative scartate**:
  - saltare su Windows i test che falliscono (la suite di chi sviluppa qui
    restava rossa, e un guasto vero si sarebbe confuso con quelli noti);
  - un solo parser per i due formati (gli avvisi avrebbero accettato
    `OCT`, un cambio di comportamento);
  - `types-rasterio` (una dipendenza in più, legata alla versione di
    rasterio, per un solo file di test dopo D-021).
- **Conseguenze**: la suite è verde anche su Windows, e un guasto solo di
  Windows si vede nella CI.


## D-023 — Il 429 è un rifiuto: per ora lo dice la documentazione

- **Data e tappa**: 2026-10-26, T19 (scelta del maintainer, concordata con
  l'agente di politefetch)
- **Contesto**: README e SKILL mettevano il 429 fra gli errori da ritentare
  presto, con `SourceNotReady`. Per chi interroga SWPC da un job, e per
  politefetch, un 429 è un rifiuto: si rallenta, non si ritenta subito.
  Mancava anche una guida per chi scarica con un livello suo e usa solo i
  parser.
- **Decisione**: il comportamento del client non cambia fino alla T17. README
  e SKILL dicono che il 429 è un rifiuto: dopo pochi tentativi distanziati ci
  si ferma fino al giro successivo del job. Una sezione nuova spiega come
  leggere le risposte HTTP a chi scarica da sé; con un livello che registra i
  fallimenti, "più tardi" vuol dire il suo giro successivo, mai un ciclo nello
  stesso processo.
- **Alternative scartate**: una classe d'errore per il 429 già nella prossima
  patch (cambia il contratto prima che la T17 lo progetti insieme
  all'errore per l'host congelato, D-016).
- **Conseguenze**: fino alla T17 il 429 si distingue solo dal messaggio, che
  la SKILL sconsiglia di leggere; la T17 gli dà un errore suo.
