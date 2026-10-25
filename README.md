# Live Scores

Live scores of your favorite teams in the Omarchy bar.

- **In the bar**: while a favorite is playing you see logos + score + minute
  (e.g. `INT 2–1 FIO 67'`). The score **pulses** when a goal is scored.
  Otherwise just a ball ``.
- **In the panel**:
  - **Live** — score with logos, FlashScore-style stats
    (possession, shots, corners, fouls, saves, cards), goal/card timeline,
    **lineups** (11 starters per side) and textual play-by-play
    **commentary** (in English, as provided by ESPN).
  - **Upcoming** — only your favorites' matches (3 days ahead),
    plus a **Results** section with finished matches.
  - **News** — news from your teams' leagues (click to open).
  - **Teams** — **search as you type** (2+ letters) across every configured
    league, with logo: press ＋ to follow, ✕ to remove, then Save.
    National teams included (search "italia").
- **Open on FlashScore** and **Gamecast ESPN** buttons for full details.

## Data

ESPN public API (`site.api.espn.com`), **no key needed**.
Covers soccer (Serie A, Premier League, LaLiga, Bundesliga, Ligue 1,
Eredivisie, Liga Portugal, Champions League, Europa League, Euros,
Nations League with national teams), basketball (NBA, EuroLeague,
Italian LBA Serie A) and hockey (NHL): hundreds of teams, but not the
lower divisions — that's the gap vs the full FlashScore database.
European basketball beyond EuroLeague (EuroCup, domestic leagues) and the
World Cup (only during the tournament) are not exposed by ESPN.

The "FlashScore-style stats" are the official match data presented the
FlashScore way; use the button for the real FlashScore page.

## Settings (also via `shell.json`)

| Key | Example |
|---|---|
| `favoriteTeams` | `inter,milan,juventus,napoli,roma` (or ESPN ids: `103,118`) |
| `leagues` | `soccer/ita.1,soccer/eng.1,…,basketball/nba,basketball/euroleague,basketball/lba,hockey/nhl` |
| `refreshIntervalSec` | `90` (30–600) |

Searchable teams: every team of the leagues above (all of Serie A, 30 NBA,
32 NHL, EuroLeague, national teams…). Free words also work (e.g. `como`).

## Requirements

- Omarchy with the Quickshell shell
- `python3` (standard library only, nothing to install)
- Internet access (ESPN API + team logos)

## Install

```bash
omarchy plugin add https://github.com/meviusisback/omarchy-live-scores
omarchy bar put meviusisback.live-scores --section left
```

Or clone this repo into `~/.config/omarchy/plugins/meviusisback.live-scores`
and rescan: `omarchy-shell shell rescanPlugins`.

## Removal

```bash
omarchy bar remove meviusisback.live-scores
rm -rf ~/.config/omarchy/plugins/meviusisback.live-scores
```

## Development

```bash
python3 tests/test_backend.py          # 22 tests, fixtures only, no network
python3 fetch_scores.py --favorites "inter,milan" --leagues "soccer/ita.1" | head -c 600
python3 fetch_scores.py --teams | head -c 300
omarchy-shell shell rescanPlugins      # reload QML after changes
```

Keys in the panel: `1–4` switch tabs, `R` refreshes, right-click on the
icon refreshes immediately.

## License

MIT — see [LICENSE](LICENSE).
