# Tappe

Una tappa per sessione cloud, una PR per tappa. Per lanciarne una basta il
prompt:

> Lavora sulla tappa Tn di `docs/TAPPE.md`, seguendo `AGENTS.md`.

Ordine: T0 e T1 in fila; poi T2–T6 anche in parallelo (toccano moduli
diversi); T7 dopo le altre; T8 per ultima.

## T0 — Impianto e ricognizione

- [x] Fatta

- `pyproject.toml` con `uv` e `hatchling`, Python ≥ 3.12, layout `src/swpc_kit/`,
  extra vuoti `client` e `geo`, configurazione di ruff, mypy (strict, su `src`
  e `tests`) e pytest.
- Moduli vuoti con docstring: `parse/`, `models/`, `export/`, `client.py`,
  `errors.py` (la gerarchia di `SPEC.md`, completa e testata).
- GitHub Actions: i cinque controlli di `AGENTS.md` su push e PR.
- `README.md` iniziale in inglese: cosa fa, stato "in sviluppo", attribuzione
  NOAA.
- **Ricognizione**: scarica da PyPI `swpclib` e `nws-aurora` (sono sui
  domini consentiti), leggi il codice e scrivi in `docs/FONTI.md` cosa coprono
  davvero. Controlla se il nome `swpc-kit` è libero su PyPI. Se una delle due
  copre già gran parte di `SPEC.md`, fermati qui e scrivilo nella PR: si
  decide prima di andare avanti.

## T1 — Fixture

- [x] Fatta

Richiede l'ambiente cloud con `services.swpc.noaa.gov` fra i domini consentiti.

- `tools/record_fixtures.py`: scarica un elenco di URL (in un file, non nel
  codice) in `tests/fixtures/<prodotto>/<AAAA-MM-GG>.<ext>` e aggiorna
  `tests/fixtures/README.md` con URL, data, dimensione.
- Registra: Kp 3 ore e previsione, Kp 1 minuto, Dst, `10cm-flux-30-day`,
  `noaa-scales`, RTSW mag e wind, GOES X-ray e protoni 1 giorno, `alerts.json`,
  i tre bollettini, OVATION, D-RAP.
- I file grandi (RTSW, OVATION) si **riducono**: si tengono le prime e ultime
  righe più un campione, con uno script che lo rifà, e si dice come in README.
  Tetto: 2 MB per tutte le fixture.
- Costruisci a mano le fixture del **vecchio formato** (array di array con
  intestazione, numeri tra virgolette) per Kp, Dst e flusso, marcate come
  costruite.
- Verifica le ipotesi di `docs/FONTI.md` che le fixture permettono di
  verificare (griglia OVATION, `Data Format`, testo dei messaggi, D-RAP) e
  aggiorna il file.

## T2 — Indici

- [x] Fatta

Parser e modelli per Kp 3 ore e previsione, Kp 1 minuto, F10.7 (30 giorni),
Dst, scale NOAA. Formati vecchi e nuovi. `data_time` su ogni modello.

## T3 — Vento solare e GOES

- [x] Fatta

- RTSW mag e plasma: modelli per campione, scelta del record attivo per
  istante, accesso alle serie per fonte.
- GOES X-ray (due bande, classe del brillamento calcolata) e protoni
  integrali per soglia di energia.

## T4 — Avvisi

- [x] Fatta

- `alerts.json` → lista di messaggi con codice corto, codice lungo, numero di
  serie, ora di emissione, validità, scala NOAA (G/S/R) quando c'è, testo.
- `swpc_kit/codes.py`: catalogo dei codici con significato e scala, e la
  corrispondenza corto ↔ lungo. Ogni voce dice se è **verificata** (dal testo
  del messaggio o dalla tabella ufficiale) o **dedotta**. Un codice
  sconosciuto non è un errore: il messaggio esce con il testo grezzo.

## T5 — Bollettini testuali

- [x] Fatta

3-day forecast, geomagnetic forecast, 27-day outlook. Un parser per
intestazione comune (`:Product:`, `:Issued:`) riusato dai tre. Gli errori
dicono la riga.

## T6 — Griglie ed export

- [x] Fatta

- OVATION e D-RAP in un modello di griglia comune (assi, valori, unità,
  tempi).
- `export.geojson`: celle sopra una soglia come poligoni, o punti; longitudini
  in -180…180.
- `export.geotiff` (extra `geo`): raster EPSG:4326 con i metadati dei tempi nei
  tag. Test che rileggono il file.

## T7 — Client

- [x] Fatta

`Client` e `AsyncClient` su `httpx` (extra `client`): un metodo per prodotto,
richieste condizionali (ETag), classificazione degli errori di `SPEC.md`,
`max_age`, timeout e user agent configurabili. Test con un trasporto finto,
senza rete.

**Prima di scegliere la dipendenza**: a ottobre 2026 httpx risultava fermo
alla 0.28.1 (dicembre 2024), con una 1.0 in sviluppo con cambi incompatibili, e
Pydantic manteneva un fork, `httpx2`. È un'informazione presa da issue di terzi,
non da una fonte primaria: verifica lo stato su PyPI e sui repo, scrivi la
scelta in `docs/FONTI.md` e tieni il client separabile dal trasporto, in modo
che cambiare libreria tocchi un modulo solo.

## T8 — Rifinitura

- [x] Fatta

README con esempi eseguibili (verificati da un test), CHANGELOG, versione
0.1.0, controllo che l'API pubblica sia esportata e documentata. Niente
pubblicazione su PyPI: si decide dopo.

## T9 — Skill per gli assistenti AI

- [x] Fatta

Il pacchetto porta con sé una skill (formato Agent Skills) che spiega a un
assistente AI come usare la libreria senza leggerne il sorgente:

- `src/swpc_kit/skill/swpc-kit/SKILL.md`, scritto a mano e leggibile anche da
  una persona: quale metodo per quale domanda, errori, tempi, trappole,
  esempi. Sotto le 500 righe.
- `references/api.md`, generato dal codice da `tools/build_skill.py`
  (prodotti, client, modelli con campi e metodi, errori, export, codici):
  l'assistente lo apre solo quando gli serve un dettaglio.
- `python -m swpc_kit.skill install | check | show | path`: copia la skill
  dove gli assistenti la cercano (`.claude/skills/swpc-kit/`) e dice se la
  copia installata è della versione del pacchetto.
- Test che tengono la skill allineata: riferimento rigenerato uguale a
  quello nel repo, versione della skill uguale a quella del pacchetto, ogni
  prodotto nella tabella, ogni nome citato esistente, esempi eseguiti.
- Versione 0.2.0.

## T10 — Schema comune delle skill dei pacchetti

- [x] Fatta

Allinea la skill di T9 allo schema "skill dei pacchetti" v1, concordato con
politefetch perché i pacchetti dello stesso autore si comportino allo stesso
modo:

- entry point `agent_skills` che punta a `swpc_kit.skill` (`bundled()`);
- `python -m swpc_kit.skill sync [--root DIR]`: installa, aggiorna (solo se
  la versione cambia) e rimuove le skill di tutti i pacchetti installati in
  `.claude/skills/`, una riga di riepilogo, uscita sempre 0, avvisi su
  stderr;
- marcatore `.package-skill` nelle copie scritte da `install` e `sync`;
  `.gitignore` con `*` solo nelle cartelle create da `sync`;
- README con l'hook `SessionStart` per il progetto che usa i pacchetti; tolto
  il suggerimento di installare in `~/.claude/skills`.

Resta nella versione 0.2.0 (il tag non era ancora stato fatto).

## T11 — Skill v2 e debiti di metodo

- [x] Fatta

Porta la skill allo standard comune delle skill di libreria (schema 1 del
modello condiviso, lo stesso che adotterà politefetch) e chiude i debiti di
metodo rimasti dalle tappe nel cloud. Toglie `sync` e l'entry point
`agent_skills` prima della prima pubblicazione, perché nessuno li adotti:

- `swpc_kit/skill/__init__.py` copiato dal modello comune (`path`, `show`,
  `check` per impronta del contenuto, `install --target` solo in
  `.claude/skills/swpc-kit` o `.agents/skills/swpc-kit`, marcatore
  `.skill-libreria.json`); un test ne confronta l'impronta con quella del
  modello. Via `sync`, `--force`, l'entry point `agent_skills`, il
  marcatore `.package-skill` e il `.gitignore` `*` nelle copie.
- `tests/test_skill.py` dal modello comune; i test di dominio (tabella dei
  prodotti, parser citati, esempi eseguiti sulle fixture) in un file
  accanto. Ogni test ha un `assert` che gli impedisce di passare a vuoto.
- Il generatore di `api.md` dal modello comune (`tools/build_skill.py`, con
  le costanti `MODULES` ed `EXTRA` di questo pacchetto). Un modulo pubblico
  nuovo, o una classe pubblica che il riferimento non descrive, fa fallire
  un test.
- La wheel costruita contiene la skill: test con `SKILL_WHEEL`, obbligatorio
  in CI su tutta la matrice.
- README, `SPEC.md` (Architettura) e CHANGELOG senza `sync`. CHANGELOG:
  0.1.0 e 0.2.0 non sono mai state pubblicate né taggate; le voci nuove
  stanno in Unreleased finché non c'è il tag.
- `docs/DECISIONI.md` a voci numerate, a partire da `httpx2` e dalla
  classificazione dei codici HTTP.
- I rinvii rimasti nel diario diventano caselle della T12.
- Prova dei difetti iniettati: almeno una mutazione per famiglia di test
  della skill, e alcune nel codice dei parser e del client.

*Esce quando*: test visti rossi con i difetti iniettati (conteggio nel Log
del diario), test della wheel verde in CI, CI verde su tutta la matrice.

Non fa parte della tappa (da concordare con politefetch): la semantica del
429 (qui `SourceNotReady`, là l'host congelato) e il client HTTP (qui
`httpx2`, là `httpx`).

## T12 — Debiti rimasti dalle tappe nel cloud

- [ ] Fatta

Rinvii scritti nel diario e mai chiusi:

- [ ] Unire il parser dei tempi testuali (`2026 Oct 13 2058 UTC`) di
  `parse/alerts.py` con quello di `parse/_text.py` in `parse/_common.py`
  (rinviato da T4 e T5 a T8, poi rimasto).
- [ ] rasterio: tenere l'override mypy (`ignore_missing_imports`) o passare
  agli stub `types-rasterio` (nuova dipendenza di sviluppo, da giustificare).
- [ ] Windows: la suite non passa tutta (async con la barriera sul socket del
  loop Proactor, griglie, esempi del README). Decidere se Windows è
  supportato; se sì, CI anche su Windows.

## Revisione prima della pubblicazione (2026-10-25)

Una revisione scettica del 25/10, fatta da un agente nuovo con circa 70
varianti delle fixture, troncature a ogni byte e script da utente nuovo, ha
trovato casi di dato sbagliato senza errore e buchi d'integrazione. Le tappe
T13–T16 li chiudono, in quest'ordine, prima della prima versione pubblica.
T13 ha la precedenza; T12 resta valida e può andare in parallelo.

Fuori dalle tappe, da concordare con politefetch prima di scrivere codice:
retry con backoff, `Retry-After`, cache dell'ETag che sopravviva al
processo (un cron oggi riscarica tutto a ogni giro). Vedi
`docs/DECISIONI.md`, D-005 e D-006.

## T13 — Niente dati sbagliati in silenzio, client senza buchi

- [x] Fatta

- [x] **Ordine e duplicati negli indici**: i parser degli indici
  (`parse/indices.py`) ordinano i record per tempo, come già fanno RTSW e
  GOES, e rifiutano i tempi duplicati con `ParseError`. Oggi un file in
  ordine inverso dà un `values[-1]` sbagliato senza errore, e README e SKILL
  insegnano proprio `values[-1]`. Controllare anche gli altri parser.
- [x] **Vento solare e `max_age`**: la freschezza si misura sulla sorgente
  attiva. Oggi `data_time` guarda tutte le sorgenti: con SOLAR1 ferma da ore
  e ACE che continua, `max_age` accetta un Bz vecchio. Scegliere fra
  `data_time` uguale all'ultimo record attivo e un `active_data_time` usato
  dal client; scriverlo in `docs/DECISIONI.md`.
- [x] **Errori del client**:
  - `_httpx.py` cattura tutti gli errori di httpx2 (`HTTPError`): oggi
    `DecodingError`, con un gzip corrotto, esce dalla gerarchia
    `SwpcError`;
  - `UnexpectedContent` ha gli attributi `status` e `location` (il nuovo
    indirizzo di un redirect sta oggi solo nel testo);
  - gli errori che passano dal client dicono prodotto e URL;
  - `swpc_kit.client` senza l'extra dice "install swpc-kit[client]",
    come già fa `export.geotiff`.
- [x] **Cambio di URL**: `fetch(product, url=...)` o un modo equivalente,
  documentato in README e SKILL; togliere dalla SKILL "no generic
  downloader" e il divieto di scaricare da sé quando l'URL è cambiato.
- [x] **Classificazione coerente con i docstring**: un prodotto sbagliato
  passato a un parser (Dst a `parse_planetary_k_index`) oggi dà
  `ParseError`, i docstring promettono `UnexpectedContent`. Allineare l'uno
  o gli altri.
- [x] **Troncature classificate male**: alcuni tagli del JSON danno
  `UnexpectedContent` invece di `SourceNotReady` (61 su 4.723 per il Kp,
  163 su 7.522 per il Dst). Ipotesi: tagli che finiscono dentro una stringa
  o dopo `\`. Verificare e correggere: un file riscritto deve dire
  "riprova".

*Esce quando*: ogni caso sopra ha un test visto rosso prima della
correzione.

## T14 — Tolleranza e plausibilità

- [ ] Fatta

**Da decidere con Paolo prima di partire**: oggi un solo record sbagliato
fa fallire l'intero prodotto, e il record resta nel file per tutta la sua
finestra (24 h il vento solare, 7 giorni il Kp, circa 30 giorni gli
avvisi). Le alternative: tolleranza per record (i record malformati in una
tupla `skipped` del modello, con il motivo) oppure "tutto o niente"
dichiarato nel README. È un cambio di contratto: dopo la prima versione
pubblica diventa incompatibile.

- [ ] La scelta, in `docs/DECISIONI.md`.
- [ ] Se tolleranza: almeno `alerts.json` (un messaggio senza
  `Serial Number:` fa cadere gli altri 80) e i campi flag di RTSW sempre
  `null` (un campo assente diventa `None`).
- [ ] **Plausibilità**: limiti su Dst, F10.7, componenti del campo
  magnetico e flusso GOES, oggi senza limiti (Dst 99999, Bz -99999, un
  flusso di 1 W/m² che diventa classe X10000 passano). I valori sentinella
  documentati da SWPC diventano `None`, gli altri fuori limite
  `ParseError`. Prima verificare in `docs/FONTI.md` quali sentinelle SWPC
  usa davvero: senza fonte è un'ipotesi.
- [ ] **Coerenza interna**: Kp a 1 minuto con `kp_index` diverso da
  `estimated_kp`; celle del 3-day forecast come `2.00 (G2)`; numeri con
  `_` accettati da `float()`.
- [ ] **Logger `swpc_kit`**: debug per i `304`, warning per i campi degli
  avvisi caduti a `None` e per i record scartati. Nessun handler
  predefinito.

## T15 — Integrazione: serializzazione, griglie, async

- [ ] Fatta

- [ ] `to_dict()` (o una funzione di `swpc_kit.export`) che dà dati pronti
  per JSON, con tempi ISO 8601 e `Z`; `to_records()` adatto a
  `pandas.DataFrame(...)` senza dipendere da pandas.
- [ ] `Grid.value_near(latitude, longitude)` (la cella più vicina): oggi
  `value_at` vuole il centro esatto e solleva `KeyError`, che non è un
  `SwpcError`. Correggere la riga della SKILL che manda a `value_at`.
- [ ] `AsyncClient`: il parse dei file grandi (OVATION, RTSW) fuori
  dall'event loop (`asyncio.to_thread`); oggi un OVATION intero lo blocca
  per circa 0,7 s.
- [ ] Timeout: dire nel docstring che vale per connessione e per lettura,
  non per l'intera richiesta, o offrire entrambi.
- [ ] Messaggi chiari per gli argomenti sbagliati di `Client` (oggi
  `timeout="30"` dà un `TypeError` grezzo).

## T16 — Pulizia per il rilascio

- [ ] Fatta

- [ ] README: stato, installazione da PyPI, peso dell'extra `geo` (circa
  140 MB con numpy; ruote di rasterio solo per macOS 15 e glibc 2.28), cosa
  succede quando SWPC cambia URL o formato (da T13 e T14).
- [ ] `SPEC.md`: l'esempio con `oval.to_geojson(threshold=10)`, che non
  esiste.
- [ ] Classifier "Development Status" adatto alla versione.
- [ ] CI con le versioni minime delle dipendenze
  (`uv sync --resolution lowest-direct`), per provare `httpx2>=2.13`,
  `numpy>=2.0`, `rasterio>=1.4`.
- [ ] Valutare un writer GeoTIFF senza rasterio (il raster è piccolo):
  solo valutazione, con la scelta in `docs/DECISIONI.md`.
- [ ] Ricontrollare che `swpc-kit` sia libero su PyPI subito prima del tag.
