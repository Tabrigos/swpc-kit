# Diario

## Da dove ripartire

Riscritto da capo a ogni fine sessione, mai accodato.

- **Stato**: T0 e T1 fatte. Fixture registrate il 2026-10-15 per tutti i
  prodotti della prima versione (543 KB, tetto 2 MiB), più esempi ufficiali
  SWPC del vecchio formato del Kp (2022) e versioni nel vecchio formato di Kp,
  Dst e flusso costruite dai file registrati. `docs/FONTI.md` riscritto con
  quello che è verificato. Nessun parser.
- **Prossimo passo**: T2–T6, anche in parallelo.
- **Da sapere**:
  - Le fixture stanno in `tests/fixtures/<prodotto>/`: `<data>.<ext>`
    registrate, `<data>-sample.<ext>` esempi ufficiali, `<data>-built.<ext>`
    costruite. Il README le elenca tutte; `tests/test_fixtures.py` controlla
    elenco, nomi e tetto.
  - `tools/record_fixtures.py` (solo libreria standard) riscarica tutto o
    alcuni prodotti da `tools/fixtures.toml`; `tools/build_old_format.py`
    ricostruisce i `*-built.json`.
  - La fixture OVATION tiene 15 longitudini intere: non è una griglia
    completa (T6 costruisce nel codice i casi della griglia intera).
  - Nel vecchio formato del Kp 3 ore il `time_tag` ha `.000`, nella
    previsione no: i parser accettano entrambe le forme.
  - RTSW: ordine decrescente, minuti senza record attivo, IMAP con orari non
    allineati al minuto (T3).
  - Avvisi: `\r\n` e `\n` mescolati, `NOAA Scale`/`Noaa Scale`; la tabella
    dei codici corti e lunghi in `FONTI.md` è verificata (T4).
  - `ParseError(message, field=, line=, index=)`; `StaleData` vuole
    `data_time` in UTC; ruff con regole `D` e `DTZ`; i test non aprono socket.
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
