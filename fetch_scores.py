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
import os
import sys
import time
import unicodedata
import urllib.request

API = "https://site.api.espn.com/apis/site/v2/sports"
REQ_TIMEOUT = 12

LEAGUES = {
    "soccer/ita.1": "Serie A",
    "soccer/eng.1": "Premier League",
    "soccer/esp.1": "LaLiga",
    "soccer/ger.1": "Bundesliga",
    "soccer/fra.1": "Ligue 1",
    "soccer/uefa.champions": "Champions League",
    "soccer/uefa.europa": "Europa League",
    "soccer/uefa.euro": "Europei",
    "soccer/uefa.nations": "Nations League",
    "soccer/ned.1": "Eredivisie",
    "soccer/por.1": "Liga Portogallo",
    "basketball/nba": "NBA",
    "basketball/euroleague": "Eurolega",
    "basketball/lba": "Serie A Basket",
    "hockey/nhl": "NHL",
}

# ESPN usa /sports/<sport>/<lega>: i valori vecchi senza sport
# (es. "ita.1") valgono come calcio per non rompere le impostazioni salvate.
def normalize_league(raw):
    raw = str(raw or "").strip()
    if "/" in raw:
        return raw if raw in LEAGUES else ""
    for key in LEAGUES:
        if key == "soccer/" + raw:
            return key
    return ""


def league_names(raw_list):
    out = []
    for item in str(raw_list or "").replace(";", ",").split(","):
        norm = normalize_league(item)
        if norm and norm not in out:
            out.append(norm)
    return out or list(LEAGUES)

# Alias italiani per le nazionali (ESPN le chiama in inglese).
NATIONAL_ALIASES = {
    "italy": ["italia"],
    "france": ["francia"],
    "spain": ["spagna"],
    "germany": ["germania"],
    "england": ["inghilterra"],
    "portugal": ["portogallo"],
    "netherlands": ["olanda", "paesi bassi"],
    "belgium": ["belgio"],
    "croatia": ["croazia"],
    "serbia": ["serbia"],
    "switzerland": ["svizzera"],
    "austria": ["austria"],
    "poland": ["polonia"],
    "denmark": ["danimarca"],
    "sweden": ["svezia"],
    "norway": ["norvegia"],
    "greece": ["grecia"],
    "turkey": ["turchia"],
    "ukraine": ["ucraina"],
    "scotland": ["scozia"],
    "wales": ["galles"],
    "romania": ["romania"],
}


def team_tokens(team):
    tokens = {fold(team.get("displayName", "")),
              fold(team.get("abbreviation", "")),
              fold(team.get("shortDisplayName", "")),
              fold(team.get("slug", "")).replace("-", " "),
              fold(team.get("location", "")),
              fold(team.get("name", ""))}
    for tok in list(tokens):
        tokens.update(NATIONAL_ALIASES.get(tok, []))
    return sorted(t for t in tokens if t)
TEAMS = [
    {"id": "inter", "label": "Inter", "league": "soccer/ita.1",
     "tokens": ["inter", "internazionale", "int"]},
    {"id": "milan", "label": "Milan", "league": "soccer/ita.1",
     "tokens": ["milan", "ac milan", "mil"]},
    {"id": "juventus", "label": "Juventus", "league": "soccer/ita.1",
     "tokens": ["juventus", "juve", "juv"]},
    {"id": "napoli", "label": "Napoli", "league": "soccer/ita.1",
     "tokens": ["napoli", "nap"]},
    {"id": "roma", "label": "Roma", "league": "soccer/ita.1",
     "tokens": ["roma", "as roma", "rom"]},
    {"id": "lazio", "label": "Lazio", "league": "soccer/ita.1",
     "tokens": ["lazio", "laz"]},
    {"id": "fiorentina", "label": "Fiorentina", "league": "soccer/ita.1",
     "tokens": ["fiorentina", "fio"]},
    {"id": "atalanta", "label": "Atalanta", "league": "soccer/ita.1",
     "tokens": ["atalanta", "ata"]},
    {"id": "bologna", "label": "Bologna", "league": "soccer/ita.1",
     "tokens": ["bologna", "bol"]},
    {"id": "torino", "label": "Torino", "league": "soccer/ita.1",
     "tokens": ["torino", "tor"]},
    {"id": "arsenal", "label": "Arsenal", "league": "soccer/eng.1",
     "tokens": ["arsenal", "ars"]},
    {"id": "liverpool", "label": "Liverpool", "league": "soccer/eng.1",
     "tokens": ["liverpool", "liv"]},
    {"id": "man-city", "label": "Man City", "league": "soccer/eng.1",
     "tokens": ["manchester city", "man city", "city", "mci"]},
    {"id": "chelsea", "label": "Chelsea", "league": "soccer/eng.1",
     "tokens": ["chelsea", "che"]},
    {"id": "man-utd", "label": "Man Utd", "league": "soccer/eng.1",
     "tokens": ["manchester united", "man utd", "manchester utd",
                "united", "mun"]},
    {"id": "tottenham", "label": "Tottenham", "league": "soccer/eng.1",
     "tokens": ["tottenham", "spurs", "tot"]},
    {"id": "real-madrid", "label": "Real Madrid", "league": "soccer/esp.1",
     "tokens": ["real madrid", "real", "rma"]},
    {"id": "barcellona", "label": "Barcellona", "league": "soccer/esp.1",
     "tokens": ["barcelona", "barcellona", "barca", "bar"]},
    {"id": "atletico", "label": "Atletico Madrid", "league": "soccer/esp.1",
     "tokens": ["atletico madrid", "atletico", "atl"]},
    {"id": "bayern", "label": "Bayern", "league": "soccer/ger.1",
     "tokens": ["bayern", "bayern monaco", "bay", "fc bayern"]},
    {"id": "dortmund", "label": "Dortmund", "league": "soccer/ger.1",
     "tokens": ["dortmund", "borussia dortmund", "bvb", "dor"]},
    {"id": "leverkusen", "label": "Leverkusen", "league": "soccer/ger.1",
     "tokens": ["leverkusen", "bayer", "lev", "bayer leverkusen"]},
    {"id": "psg", "label": "PSG", "league": "soccer/fra.1",
     "tokens": ["psg", "paris", "parigi", "paris saint-germain"]},
    {"id": "marsiglia", "label": "Marsiglia", "league": "soccer/fra.1",
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


def http_get_json(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "omarchy-live-scores/1.0"})
            with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:
            last = exc
            time.sleep(1 + attempt)
    raise last


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
    logos = team.get("logos") or []
    logo = team.get("logo", "") or (logos[0].get("href", "") if logos else "")
    return {
        "id": str(team.get("id", "")),
        "name": team.get("displayName", "?"),
        "abbr": team.get("abbreviation", "?"),
        "score": comp.get("score", "0"),
        "logo": logo,
        "winner": bool(comp.get("winner")),
    }


def espn_link(league, event_id):
    sport = league.split("/")[0] if "/" in league else "soccer"
    # Il calcio ha la pagina "match", gli altri sport la pagina "game".
    kind = "match" if sport == "soccer" else "game"
    return "https://www.espn.com/{}/{}/_/gameId/{}".format(sport, kind, event_id)


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
        "espnLink": espn_link(league, event.get("id", "")),
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
    id_favs = set(favorites)  # gli id ESPN numerici si confrontano diretti
    leagues = league_names(leagues_raw)

    today = dt.date.today()
    jobs = [(league, None) for league in leagues]
    # ESPN mostra solo la giornata in corso: guardo anche i prossimi
    # 3 giorni così "Prossime" ha sempre qualcosa da far vedere.
    for offset in (1, 2, 3):
        day = (today + dt.timedelta(days=offset)).strftime("%Y%m%d")
        jobs.extend((league, day) for league in leagues)

    boards = {}
    with futures.ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
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
            if favorites and not (
                    match["home"].get("id") in id_favs
                    or match["away"].get("id") in id_favs
                    or (tokens and is_favorite_match(
                        [{"team": {"displayName": match["home"]["name"],
                                   "abbreviation": match["home"]["abbr"]}},
                         {"team": {"displayName": match["away"]["name"],
                                   "abbreviation": match["away"]["abbr"]}}], tokens))):
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

    # Notizie dai campionati coinvolti (preferite in campo o scelte),
    # altrimenti Serie A.
    fav_leagues = []
    for fav in favorites:
        team = next((t for t in TEAMS if t["id"] == fav), None)
        if team and team["league"] in leagues and team["league"] not in fav_leagues:
            fav_leagues.append(team["league"])
    for match in live + upcoming + results:
        if match["league"] not in fav_leagues:
            fav_leagues.append(match["league"])
    news = []
    for league in (fav_leagues or ["soccer/ita.1"]):
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
        return {s.get("name"): s.get("displayValue")
                for s in by_side.get(side, {}).get("statistics", [])}

    # Solo le righe che esistono davvero (calcio, basket e hockey
    # espongono statistiche diverse): niente righe vuote.
    home_raw = stats_for("home")
    away_raw = stats_for("away")
    stats = []
    for label, key in STAT_ROWS:
        home, away = home_raw.get(key), away_raw.get(key)
        if home is None and away is None:
            continue
        stats.append({"label": label, "home": home if home is not None else "–",
                      "away": away if away is not None else "–"})

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

    # Formazioni: 11 titolari per parte (numero, nome, ruolo).
    lineups = []
    for entry in data.get("rosters", []) or []:
        side = entry.get("homeAway", "")
        roster = entry.get("roster", []) or []
        starters = [p for p in roster if p.get("starter")] or roster[:11]
        players = []
        for p in starters:
            athlete = p.get("athlete") or {}
            pos = p.get("position") or {}
            players.append({
                "num": str(p.get("jersey", "")),
                "name": athlete.get("shortName") or athlete.get("displayName", "?"),
                "pos": pos.get("abbreviation", ""),
            })
        team = entry.get("team") or {}
        lineups.append({"side": side,
                        "team": team.get("abbreviation", ""),
                        "players": players[:11]})

    # Cronaca testuale (play-by-play), dalla più recente.
    commentary = []
    for item in data.get("commentary", []) or []:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        commentary.append({
            "clock": ((item.get("time") or {}).get("displayValue") or ""),
            "text": text[:300],
        })
    commentary = commentary[-15:][::-1]

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
            "lineups": lineups, "commentary": commentary,
            "news": news, "error": ""}


def fetch_league_teams(league):
    """Tutte le squadre di un campionato, con logo: è il catalogo cercabile."""
    try:
        data = http_get_json("{}/{}/teams?limit=100".format(API, league))
    except Exception as exc:
        sys.stderr.write("live-scores teams {}: {}\n".format(league, exc))
        return []
    n_sports = len(data.get("sports", []))
    out = []
    for sport in data.get("sports", []):
        for lg in sport.get("leagues", []):
            for entry in lg.get("teams", []):
                team = entry.get("team", {})
                logos = [l.get("href", "") for l in team.get("logos", [])
                         if "dark" not in str(l.get("rel", ""))]
                out.append({
                    "id": str(team.get("id", "")),
                    "label": team.get("displayName", "?"),
                    "league": league,
                    "logo": logos[0] if logos else "",
                    "tokens": team_tokens(team),
                })
    sys.stderr.write("live-scores teams {}: {} sports -> {} squadre\n".format(league, n_sports, len(out)))
    return out


def teams_payload(leagues_raw):
    leagues = league_names(leagues_raw)
    catalog, seen = [], set()
    with futures.ThreadPoolExecutor(max_workers=min(4, len(leagues))) as pool:
        for teams in pool.map(safe_teams, leagues):
            for team in teams:
                key = (team["league"], team["id"])
                if key not in seen:
                    seen.add(key)
                    catalog.append(team)
    # Cache su disco: se una lega stavolta torna vuota (singhiozzo ESPN),
    # riusa le squadre salvate invece di far sparire mezza ricerca.
    catalog = merge_teams_cache(leagues, catalog)
    if not catalog:
        # Offline totale: almeno le preferite classiche restano selezionabili.
        catalog = [{"id": t["id"], "label": t["label"], "league": t["league"],
                    "logo": "", "tokens": t["tokens"]} for t in TEAMS]
    catalog.sort(key=lambda t: (t["league"], t["label"]))
    return {"teams": catalog}


def safe_teams(league):
    """Una lega rotta non deve mai abortire le altre nove."""
    try:
        return fetch_league_teams(league)
    except Exception as exc:
        sys.stderr.write("live-scores teams {}: FATAL {}\n".format(league, exc))
        return []


def teams_cache_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "omarchy-live-scores", "teams.json")


def merge_teams_cache(leagues, fresh):
    try:
        with open(teams_cache_path(), encoding="utf-8") as fh:
            cached = json.load(fh)
    except Exception:
        cached = []
    if not isinstance(cached, list):
        cached = []
    fresh_keys = set((t["league"], t["id"]) for t in fresh)
    merged = list(fresh)
    for team in cached:
        key = (team.get("league"), team.get("id"))
        if team.get("league") in leagues and key not in fresh_keys:
            merged.append(team)
            fresh_keys.add(key)
    try:
        path = teams_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False)
    except Exception as exc:
        sys.stderr.write("live-scores cache: {}\n".format(exc))
    return merged


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--favorites", default="inter,juventus,milan,napoli,roma")
    parser.add_argument("--leagues", default=",".join(LEAGUES))
    parser.add_argument("--summary", nargs=2, metavar=("LEAGUE", "EVENT_ID"))
    parser.add_argument("--teams", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.teams:
            payload = teams_payload(args.leagues)
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
