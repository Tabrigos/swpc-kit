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

- [ ] Fatta

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

- [ ] Fatta

Parser e modelli per Kp 3 ore e previsione, Kp 1 minuto, F10.7 (30 giorni),
Dst, scale NOAA. Formati vecchi e nuovi. `data_time` su ogni modello.

## T3 — Vento solare e GOES

- [ ] Fatta

- RTSW mag e plasma: modelli per campione, scelta del record attivo per
  istante, accesso alle serie per fonte.
- GOES X-ray (due bande, classe del brillamento calcolata) e protoni
  integrali per soglia di energia.

## T4 — Avvisi

- [ ] Fatta

- `alerts.json` → lista di messaggi con codice corto, codice lungo, numero di
  serie, ora di emissione, validità, scala NOAA (G/S/R) quando c'è, testo.
- `swpc_kit/codes.py`: catalogo dei codici con significato e scala, e la
  corrispondenza corto ↔ lungo. Ogni voce dice se è **verificata** (dal testo
  del messaggio o dalla tabella ufficiale) o **dedotta**. Un codice
  sconosciuto non è un errore: il messaggio esce con il testo grezzo.

## T5 — Bollettini testuali

- [ ] Fatta

3-day forecast, geomagnetic forecast, 27-day outlook. Un parser per
intestazione comune (`:Product:`, `:Issued:`) riusato dai tre. Gli errori
dicono la riga.

## T6 — Griglie ed export

- [ ] Fatta

- OVATION e D-RAP in un modello di griglia comune (assi, valori, unità,
  tempi).
- `export.geojson`: celle sopra una soglia come poligoni, o punti; longitudini
  in -180…180.
- `export.geotiff` (extra `geo`): raster EPSG:4326 con i metadati dei tempi nei
  tag. Test che rileggono il file.

## T7 — Client

- [ ] Fatta

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

- [ ] Fatta

README con esempi eseguibili (verificati da un test), CHANGELOG, versione
0.1.0, controllo che l'API pubblica sia esportata e documentata. Niente
pubblicazione su PyPI: si decide dopo.
