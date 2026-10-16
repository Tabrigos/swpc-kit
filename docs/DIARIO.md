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
- 2026-10-16 — T5 (sub-agente, branch `-t5`): 3-day forecast, geomagnetic
  forecast e 27-day outlook con lettore comune dell'intestazione.
