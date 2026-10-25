# Live Scores

Risultati live delle tue squadre preferite nella barra di Omarchy.

- **Nella barra**: quando gioca una preferita vedi loghi + punteggio + minuto
  (es. `INT 2–1 FIO 67'`). Al gol il punteggio **pulsa**. Altrimenti un pallone ``.
- **Nel pannello**:
  - **Diretta** — punteggio con loghi, statistiche stile FlashScore
    (possesso, tiri, angoli, falli, parate, cartellini), cronaca gol/cartellini,
    **formazioni** (11 titolari per parte) e **cronaca testuale** play-by-play
    (in inglese, come la fornisce ESPN), risultati di oggi e — se non c'è
    nessuna diretta — anteprima prossime partite.
  - **Prossime** — calendario delle preferite (3 giorni in avanti).
  - **Notizie** — notizie dai campionati delle tue squadre (clic per aprire).
  - **Squadre** — **cerca mentre digiti** (2+ lettere) tra tutte le squadre
    dei campionati configurati, col logo: premi ＋ per seguire, ✕ per togliere,
    poi Salva.
- Pulsanti **Apri su FlashScore** e **Gamecast ESPN** per i dettagli online.

## Dati

API pubblica ESPN (`site.api.espn.com`), **senza chiave**.
Copre calcio (Serie A, Premier League, LaLiga, Bundesliga, Ligue 1,
Champions, Europa League), basket (NBA, Eurolega) e hockey (NHL):
centinaia di squadre, ma non le serie minori — quello è il limite
rispetto al database completo di FlashScore.

Le "statistiche stile FlashScore" sono i dati ufficiali della partita
presentati come su FlashScore; per la pagina FlashScore vera usa il pulsante.

## Impostazioni (anche da `shell.json`)

| Chiave | Esempio |
|---|---|
| `favoriteTeams` | `inter,milan,juventus,napoli,roma` (o id ESPN: `103,118`) |
| `leagues` | `soccer/ita.1,soccer/eng.1,…,basketball/nba,basketball/euroleague,hockey/nhl` |
| `refreshIntervalSec` | `90` (min 30) |

Squadre cercabili: tutte quelle dei campionati sopra (Serie A al completo,
30 NBA, 32 NHL, Eurolega…). Puoi anche scrivere parole libere (es. `como`).

## Sviluppo

```bash
python3 tests/test_backend.py          # 8 test, dati finti, niente rete
python3 fetch_scores.py --favorites "inter,milan" --leagues "ita.1" | head -c 600
python3 fetch_scores.py --teams | head -c 300
omarchy-shell shell rescanPlugins      # ricarica il QML dopo modifiche
```

Tasti nel pannello: `1–4` cambiano tab, `R` aggiorna, click destro
sull'icona aggiorna subito.
