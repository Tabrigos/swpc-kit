# Diario

## Da dove ripartire

Riscritto da capo a ogni fine sessione, mai accodato.

- **Stato**: T0 fatta. Impianto `uv` + `hatchling`, layout `src/swpc_kit/`,
  moduli vuoti, gerarchia degli errori in `errors.py` completa e testata, CI
  su GitHub Actions (Python 3.12 e 3.13). Nessun parser.
- **Prossimo passo**: T1 (fixture). `services.swpc.noaa.gov` è ora fra i
  domini consentiti dell'ambiente cloud.
- **Da sapere**:
  - `ParseError(message, field=, line=, index=)`: `line` è 1-based (testi),
    `index` 0-based (record di un array JSON).
  - `StaleData` vuole `data_time` in UTC.
  - Ruff ha le regole `D` (docstring Google, non nei test) e `DTZ` (niente
    datetime senza fuso).
  - Un `conftest.py` blocca i socket nei test.
  - `ruff format` formatta anche i blocchi Python nei `.md`.
- **Dubbi aperti**: le ipotesi segnate in `docs/FONTI.md`. Gli esempi di
  avvisi del 2022 trovati in `swpclib` rafforzano la corrispondenza dei codici
  corti e lunghi, ma vanno confermati sulla fixture.

## Log

Una riga per sessione: data, tappa, cosa è entrato, cosa resta.

- 2026-10-15 — progetto avviato: `SPEC.md`, `docs/FONTI.md` (ricognizione dei
  prodotti SWPC e delle librerie esistenti), `docs/TAPPE.md`.
- 2026-10-15 — T0: impianto, errori, CI, README. Ricognizione di `swpclib` e
  `nws-aurora` (nessuna copre la specifica; nome `swpc-kit` libero su PyPI).
  Resta: T1.
