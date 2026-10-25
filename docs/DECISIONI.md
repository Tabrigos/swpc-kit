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
