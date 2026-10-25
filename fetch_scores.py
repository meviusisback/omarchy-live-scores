#!/usr/bin/env python3
"""Risultati live per la barra di Omarchy.

Legge i tabelloni dei campionati dall'API pubblica di ESPN
(site.api.espn.com, senza chiave) e stampa un JSON con:
  live      partite in diretta delle squadre preferite
  upcoming  prossime partite delle preferite
  results   risultati di oggi delle preferite (finite)
  news      notizie dai campionati delle preferite

Uso:
  fetch_scores.py --favorites "inter,juventus" --leagues "ita.1,eng.1"
  fetch_scores.py --summary ita.1 401875036   # statistiche stile FlashScore
  fetch_scores.py --teams                       # catalogo squadre selezionabili
"""

import argparse
import concurrent.futures as futures
import datetime as dt
import json
import sys
import unicodedata
import urllib.request

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
REQ_TIMEOUT = 12

LEAGUES = {
    "ita.1": "Serie A",
    "eng.1": "Premier League",
    "esp.1": "LaLiga",
    "ger.1": "Bundesliga",
    "fra.1": "Ligue 1",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
}

# Catalogo squadre: id stabile, etichetta, campionato, chiavi di ricerca
# (nomi it/en + abbreviazioni ESPN).
TEAMS = [
    {"id": "inter", "label": "Inter", "league": "ita.1",
     "tokens": ["inter", "internazionale", "int"]},
    {"id": "milan", "label": "Milan", "league": "ita.1",
     "tokens": ["milan", "ac milan", "mil"]},
    {"id": "juventus", "label": "Juventus", "league": "ita.1",
     "tokens": ["juventus", "juve", "juv"]},
    {"id": "napoli", "label": "Napoli", "league": "ita.1",
     "tokens": ["napoli", "nap"]},
    {"id": "roma", "label": "Roma", "league": "ita.1",
     "tokens": ["roma", "as roma", "rom"]},
    {"id": "lazio", "label": "Lazio", "league": "ita.1",
     "tokens": ["lazio", "laz"]},
    {"id": "fiorentina", "label": "Fiorentina", "league": "ita.1",
     "tokens": ["fiorentina", "fio"]},
    {"id": "atalanta", "label": "Atalanta", "league": "ita.1",
     "tokens": ["atalanta", "ata"]},
    {"id": "bologna", "label": "Bologna", "league": "ita.1",
     "tokens": ["bologna", "bol"]},
    {"id": "torino", "label": "Torino", "league": "ita.1",
     "tokens": ["torino", "tor"]},
    {"id": "arsenal", "label": "Arsenal", "league": "eng.1",
     "tokens": ["arsenal", "ars"]},
    {"id": "liverpool", "label": "Liverpool", "league": "eng.1",
     "tokens": ["liverpool", "liv"]},
    {"id": "man-city", "label": "Man City", "league": "eng.1",
     "tokens": ["manchester city", "man city", "city", "mci"]},
    {"id": "chelsea", "label": "Chelsea", "league": "eng.1",
     "tokens": ["chelsea", "che"]},
    {"id": "man-utd", "label": "Man Utd", "league": "eng.1",
     "tokens": ["manchester united", "man utd", "manchester utd",
                "united", "mun"]},
    {"id": "tottenham", "label": "Tottenham", "league": "eng.1",
     "tokens": ["tottenham", "spurs", "tot"]},
    {"id": "real-madrid", "label": "Real Madrid", "league": "esp.1",
     "tokens": ["real madrid", "real", "rma"]},
    {"id": "barcellona", "label": "Barcellona", "league": "esp.1",
     "tokens": ["barcelona", "barcellona", "barca", "bar"]},
    {"id": "atletico", "label": "Atletico Madrid", "league": "esp.1",
     "tokens": ["atletico madrid", "atletico", "atl"]},
    {"id": "bayern", "label": "Bayern", "league": "ger.1",
     "tokens": ["bayern", "bayern monaco", "bay", "fc bayern"]},
    {"id": "dortmund", "label": "Dortmund", "league": "ger.1",
     "tokens": ["dortmund", "borussia dortmund", "bvb", "dor"]},
    {"id": "leverkusen", "label": "Leverkusen", "league": "ger.1",
     "tokens": ["leverkusen", "bayer", "lev", "bayer leverkusen"]},
    {"id": "psg", "label": "PSG", "league": "fra.1",
     "tokens": ["psg", "paris", "parigi", "paris saint-germain"]},
    {"id": "marsiglia", "label": "Marsiglia", "league": "fra.1",
     "tokens": ["marsiglia", "marseille", "om"]},
]

# Statistiche ESPN -> righe stile FlashScore (etichetta, chiave ESPN).
STAT_ROWS = [
    ("Possesso %", "possessionPct"),
    ("Tiri totali", "totalShots"),
    ("Tiri in porta", "shotsOnTarget"),
    ("Calci d'angolo", "wonCorners"),
    ("Falli", "foulsCommitted"),
    ("Fuorigioco", "offsides"),
    ("Parate", "saves"),
    ("Ammonizioni", "yellowCards"),
    ("Espulsioni", "redCards"),
]


def fold(text):
    """Minuscole senza accenti, per confrontare 'atletico' con 'atlético'."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "omarchy-live-scores/1.0"})
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def parse_favorites(raw):
    return [fold(p.strip()) for p in str(raw or "").replace(";", ",").split(",") if p.strip()]


def favorite_tokens(favorites):
    """Id del catalogo -> chiavi di ricerca; id sconosciuti usati così come sono."""
    by_id = {t["id"]: t for t in TEAMS}
    out = []
    for fav in favorites:
        team = by_id.get(fav)
        out.extend(team["tokens"] if team else [fav])
    return out


def competitor_info(comp):
    team = comp.get("team", {})
    return {
        "name": team.get("displayName", "?"),
        "abbr": team.get("abbreviation", "?"),
        "score": comp.get("score", "0"),
        "logo": team.get("logo", ""),
        "winner": bool(comp.get("winner")),
    }


def is_favorite_match(comps, tokens):
    hay = " ".join(
        fold(c.get("team", {}).get("displayName", "")) + " "
        + fold(c.get("team", {}).get("abbreviation", ""))
        for c in comps
    )
    return any(tok and tok in hay for tok in tokens)


def normalize_event(league, event):
    comp = (event.get("competitions") or [{}])[0]
    comps = comp.get("competitors", [])
    home = next((c for c in comps if c.get("homeAway") == "home"), comps[0] if comps else {})
    away = next((c for c in comps if c.get("homeAway") == "away"), comps[1] if len(comps) > 1 else {})
    status = event.get("status", {})
    stype = status.get("type", {})
    return {
        "id": str(event.get("id", "")),
        "league": league,
        "leagueName": LEAGUES.get(league, league),
        "home": competitor_info(home),
        "away": competitor_info(away),
        "state": stype.get("state", ""),  # in = diretta, pre, post = finita
        "detail": stype.get("shortDetail") or stype.get("detail") or "",
        "clock": status.get("displayClock", ""),
        "date": event.get("date", ""),
        "espnLink": "https://www.espn.com/soccer/match/_/gameId/{}".format(event.get("id", "")),
    }


def fetch_league_board(league, date=None):
    url = "{}/{}/scoreboard".format(API, league)
    if date:
        url += "?dates=" + date
    try:
        data = http_get_json(url)
        return league, [normalize_event(league, e) for e in data.get("events", [])]
    except Exception as exc:  # rete giù: la lega salta, le altre restano
        sys.stderr.write("live-scores: {} {}: {}\n".format(league, date or "", exc))
        return league, []


def fetch_news(league, limit=6):
    try:
        data = http_get_json("{}/{}/news?limit={}".format(API, league, limit))
        out = []
        for art in data.get("articles", [])[:limit]:
            links = art.get("links", {})
            web = links.get("web", {}) if isinstance(links, dict) else {}
            out.append({
                "headline": art.get("headline", ""),
                "description": (art.get("description", "") or "")[:180],
                "link": web.get("href", ""),
                "published": art.get("published", ""),
                "league": LEAGUES.get(league, league),
            })
        return out
    except Exception as exc:
        sys.stderr.write("live-scores news {}: {}\n".format(league, exc))
        return []


def scoreboard_payload(favorites_raw, leagues_raw):
    favorites = parse_favorites(favorites_raw)
    tokens = favorite_tokens(favorites)
    leagues = [l.strip() for l in str(leagues_raw or "").replace(";", ",").split(",")]
    leagues = [l for l in leagues if l in LEAGUES] or list(LEAGUES)

    today = dt.date.today()
    jobs = [(league, None) for league in leagues]
    # ESPN mostra solo la giornata in corso: guardo anche i prossimi
    # 3 giorni così "Prossime" ha sempre qualcosa da far vedere.
    for offset in (1, 2, 3):
        day = (today + dt.timedelta(days=offset)).strftime("%Y%m%d")
        jobs.extend((league, day) for league in leagues)

    boards = {}
    with futures.ThreadPoolExecutor(max_workers=min(16, len(jobs))) as pool:
        for league, matches in pool.map(lambda j: fetch_league_board(*j), jobs):
            boards.setdefault(league, []).extend(matches)
    # Stessa partita su più giorni: tengo la prima occorrenza.
    for league in boards:
        seen, uniq = set(), []
        for match in boards[league]:
            if match["id"] not in seen:
                seen.add(match["id"])
                uniq.append(match)
        boards[league] = uniq

    live, upcoming, results = [], [], []
    for league in leagues:
        for match in boards.get(league, []):
            if tokens and not is_favorite_match(
                    [{"team": {"displayName": match["home"]["name"],
                               "abbreviation": match["home"]["abbr"]}},
                     {"team": {"displayName": match["away"]["name"],
                               "abbreviation": match["away"]["abbr"]}}], tokens):
                continue
            if match["state"] == "in":
                live.append(match)
            elif match["state"] == "pre":
                upcoming.append(match)
            else:
                results.append(match)

    upcoming.sort(key=lambda m: m["date"])
    # Le dirette prima per minuto (le più avanzate in alto).
    live.sort(key=lambda m: m["clock"], reverse=True)

    fav_leagues = []
    for fav in favorites:
        team = next((t for t in TEAMS if t["id"] == fav), None)
        if team and team["league"] in leagues and team["league"] not in fav_leagues:
            fav_leagues.append(team["league"])
    news = []
    for league in (fav_leagues or ["ita.1"]):
        news.extend(fetch_news(league, limit=5))
    news = news[:10]

    return {"live": live, "upcoming": upcoming[:10], "results": results[:10],
            "news": news, "error": ""}


def summary_payload(league, event_id):
    data = http_get_json("{}/{}/summary?event={}".format(API, league, event_id))
    header = (data.get("header", {}).get("competitions") or [{}])[0]
    teams = data.get("boxscore", {}).get("teams", [])
    by_side = {t.get("homeAway"): t for t in teams}

    def stats_for(side):
        raw = {s.get("name"): s.get("displayValue")
               for s in by_side.get(side, {}).get("statistics", [])}
        rows = []
        for label, key in STAT_ROWS:
            rows.append({"label": label, "home": raw.get(key, "–"),
                         "away": raw.get(key, "–")})
        return rows

    # Unisce le due colonne: ogni riga ha valore casa e trasferta.
    home_stats = {s["label"]: s["home"] for s in stats_for("home")}
    away_stats = {s["label"]: s["away"] for s in stats_for("away")}
    stats = [{"label": label, "home": home_stats.get(label, "–"),
              "away": away_stats.get(label, "–")} for label, _ in STAT_ROWS]

    timeline = []
    for det in header.get("details", []):
        clock = (det.get("clock") or {}).get("displayValue", "")
        if det.get("scoringPlay"):
            kind, what = ("penalty" if det.get("penaltyKick") else "goal",
                          "Gol su rigore" if det.get("penaltyKick") else "Gol")
        elif det.get("redCard"):
            kind, what = "card", "Espulsione"
        elif det.get("yellowCard"):
            kind, what = "card", "Ammonizione"
        else:
            kind, what = "info", "Evento"
        athletes = " · ".join(
            (p.get("athlete") or {}).get("displayName", "")
            for p in det.get("participants", []) if isinstance(p, dict))
        text = "{} {}".format(clock, what).strip()
        if athletes:
            text += " — " + athletes
        timeline.append({
            "clock": clock, "text": text, "kind": kind,
            "team": (det.get("team") or {}).get("abbreviation", ""),
        })

    news = [{
        "headline": a.get("headline", ""),
        "description": (a.get("description", "") or "")[:180],
        "link": ((a.get("links") or {}).get("web") or {}).get("href", ""),
        "published": a.get("published", ""),
        "league": "",
    } for a in (data.get("news", {}).get("articles", []) or [])[:5]]

    events = [e for e in [normalize_event(league, header)] if e["id"]]
    match = events[0] if events else {}
    if match:
        # Lo scoreboard "header" non ha i punteggi: li prendo dai competitors.
        comps = header.get("competitors", [])
        for side, key in (("home", "home"), ("away", "away")):
            comp = next((c for c in comps if c.get("homeAway") == side), {})
            if comp:
                match[key] = competitor_info(comp)
    return {"match": match, "stats": stats, "timeline": timeline,
            "news": news, "error": ""}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--favorites", default="inter,juventus,milan,napoli,roma")
    parser.add_argument("--leagues", default=",".join(LEAGUES))
    parser.add_argument("--summary", nargs=2, metavar=("LEAGUE", "EVENT_ID"))
    parser.add_argument("--teams", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.teams:
            payload = {"teams": TEAMS}
        elif args.summary:
            payload = summary_payload(args.summary[0], args.summary[1])
        else:
            payload = scoreboard_payload(args.favorites, args.leagues)
    except Exception as exc:
        payload = {"live": [], "upcoming": [], "results": [], "news": [],
                   "error": str(exc)[:200]}
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
