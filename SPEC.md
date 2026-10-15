# swpc-kit — specifica

## Obiettivo

Una libreria Python che trasforma i prodotti pubblici di NOAA SWPC
(`services.swpc.noaa.gov`) in modelli tipizzati, affidabili quando la fonte
cambia formato, si ferma o risponde male, e che esporta le griglie (OVATION,
D-RAP) in GeoJSON e GeoTIFF.

Chi la usa: un backend che ingerisce dati di meteo spaziale (per esempio un
servizio FastAPI), uno script di analisi, un notebook.

## Cosa non fa

- Niente grafici, niente interfaccia, niente database o cache su disco.
- Niente modelli fisici o previsioni proprie: legge quello che pubblica SWPC.
- Niente prodotti di altri enti (NASA DONKI, iSWA, GFZ) nella prima versione.
- Niente immagini (coronografi, SUVI, animazioni).

## Architettura

Tre strati, ognuno usabile da solo:

1. **Parser** (`swpc_kit.parse.*`): funzioni pure, `str | bytes` → modello.
   Solo libreria standard.
2. **Modelli** (`swpc_kit.models.*`): dataclass congelate, tipizzate, con
   `datetime` UTC. Ogni prodotto ha un modello con `issued` / `observed` /
   `valid_from` / `valid_to` dove la fonte li dà, e `source_url`.
3. **Uscite**:
   - `swpc_kit.export.geojson` (libreria standard);
   - `swpc_kit.export.geotiff` (extra `geo`, con `numpy` e `rasterio`);
   - `swpc_kit.client` (extra `client`, con `httpx`): scarica, riconosce gli
     errori della fonte, chiama il parser.

```python
from swpc_kit.parse import parse_planetary_k_index
from swpc_kit.client import Client

kp = parse_planetary_k_index(raw_bytes)  # senza rete
with Client() as c:
    kp = c.planetary_k_index()  # con rete
    oval = c.ovation_aurora()
    oval.to_geojson(threshold=10)
```

I nomi esatti si decidono nelle tappe; questo è l'impianto.

## Prodotti della prima versione

| Gruppo | Prodotti | Tappa |
|---|---|---|
| Indici | Kp 3 ore e previsione, Kp 1 minuto, F10.7, Dst di Kyoto, scale NOAA (`noaa-scales.json`) | T2 |
| Vento solare | RTSW mag e plasma 1 minuto (SOLAR-1, ACE), con scelta della fonte attiva | T3 |
| GOES | flusso X (con classe del brillamento A/B/C/M/X), protoni integrali | T3 |
| Avvisi | `alerts.json`, parsing del testo dei messaggi, catalogo dei codici | T4 |
| Bollettini | 3-day forecast, geomagnetic forecast, 27-day outlook | T5 |
| Griglie | OVATION aurora, D-RAP | T6 |

## Errori

Una gerarchia sotto `SwpcError`:

- `SourceNotReady`: dato troncato o vuoto (JSON non chiuso, file a metà).
  Succede davvero: SWPC a volte serve un file mentre lo riscrive. È uno stato
  transitorio, non un bug: chi chiama riprova più tardi.
- `UnexpectedContent`: la fonte risponde con altro (una pagina HTML, un
  redirect verso una pagina di annunci, un formato che nessun parser conosce).
- `ParseError`: il formato è quello atteso ma un campo è incoerente. Il
  messaggio dice quale campo e quale riga.
- `StaleData` (solo nel client, e solo se chi chiama passa un'età massima):
  il dato è più vecchio del previsto.

## Freschezza

L'età del dato si misura **sul tempo che dichiara il contenuto** (`Observation
Time`, `:Issued:`, l'ultimo `time_tag`), mai sull'esito HTTP: un `304 Not
Modified` o una data di modifica recente non dicono che il dato è nuovo. Ogni
modello espone `data_time` (il tempo più recente del contenuto), e il client
accetta `max_age`.

## Formati che cambiano

SWPC cambia i formati con preavviso (le SCN, *Service Change Notices*). Nel
2026 il Kp a 3 ore e altri prodotti sono passati da "array di array con la
riga d'intestazione" a "array di oggetti", con i numeri non più tra
virgolette. Un parser riconosce **tutti** i formati documentati in
`docs/FONTI.md` e restituisce lo stesso modello.

## Qualità

- Python 3.12 o successivo; `uv` per ambiente e build (`hatchling`).
- `mypy --strict`, `ruff check`, `ruff format`, `pytest` puliti; CI su GitHub
  Actions che esegue gli stessi comandi.
- Ogni parser ha test su fixture reali e su casi limite costruiti a mano
  (campo mancante, troncato, valori fuori scala, fonte inattiva).
- API pubblica documentata nelle docstring; README con esempi eseguibili.

## Licenza

Da decidere quando il repo diventa pubblico. I dati SWPC sono pubblici; NOAA
chiede l'attribuzione e di non implicare un suo avallo: il README lo dirà.
