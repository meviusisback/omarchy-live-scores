# Live Scores

Risultati live delle tue squadre preferite nella barra di Omarchy.

- **Nella barra**: quando gioca una preferita vedi loghi + punteggio + minuto
  (es. `INT 2–1 FIO 67'` con pallino rosso). Altrimenti un pallone ``.
- **Nel pannello**:
  - **Diretta** — punteggio con loghi, statistiche stile FlashScore
    (possesso, tiri, angoli, falli, parate, cartellini), cronaca gol/cartellini,
    risultati di oggi e — se non c'è nessuna diretta — anteprima prossime partite.
  - **Prossime** — calendario delle preferite.
  - **Notizie** — notizie dai campionati delle tue squadre (clic per aprire).
  - **Squadre** — scegli le preferite e premi Salva.
- Pulsanti **Apri su FlashScore** e **Gamecast ESPN** per i dettagli online.

## Dati

API pubblica ESPN (`site.api.espn.com`), **senza chiave**.
Copre Serie A, Premier League, LaLiga, Bundesliga, Ligue 1,
Champions ed Europa League. Aggiornamento ogni 90 secondi (configurabile).

Le "statistiche stile FlashScore" sono i dati ufficiali della partita
presentati come su FlashScore; per la pagina FlashScore vera usa il pulsante.

## Impostazioni (anche da `shell.json`)

| Chiave | Esempio |
|---|---|
| `favoriteTeams` | `inter,milan,juventus,napoli,roma` |
| `leagues` | `ita.1,eng.1,esp.1,ger.1,fra.1,uefa.champions,uefa.europa` |
| `refreshIntervalSec` | `90` (min 30) |

Squadre selezionabili: inter, milan, juventus, napoli, roma, lazio,
fiorentina, atalanta, bologna, torino, arsenal, liverpool, man-city,
chelsea, man-utd, tottenham, real-madrid, barcellona, atletico,
bayern, dortmund, leverkusen, psg, marsiglia.
Puoi anche scrivere parole libere (es. `como`).

## Sviluppo

```bash
python3 tests/test_backend.py          # 8 test, dati finti, niente rete
python3 fetch_scores.py --favorites "inter,milan" --leagues "ita.1" | head -c 600
python3 fetch_scores.py --teams | head -c 300
omarchy-shell shell rescanPlugins      # ricarica il QML dopo modifiche
```

Tasti nel pannello: `1–4` cambiano tab, `R` aggiorna, click destro
sull'icona aggiorna subito.
