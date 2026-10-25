"""Test del backend live-scores: solo dati finti, niente rete."""
import sys
import unittest

sys.path.insert(0, "..")
import fetch_scores as fs


def fake_comp(name, abbr, score, home_away, tid="0"):
    return {"homeAway": home_away, "score": score,
            "team": {"id": tid, "displayName": name, "abbreviation": abbr,
                     "logo": "https://x/{}.png".format(abbr)}}


def fake_event(eid="1", state="in", clock="67'", detail="2nd Half - 67'"):
    return {"id": eid, "date": "2026-10-25T18:00Z",
            "status": {"displayClock": clock,
                       "type": {"state": state, "shortDetail": detail,
                                "detail": detail}},
            "competitions": [{"competitors": [
                fake_comp("Internazionale", "INT", "2", "home", "110"),
                fake_comp("Juventus", "JUV", "1", "away", "111")]}]}


class TestLeagues(unittest.TestCase):
    def test_bare_slug_diventa_calcio(self):
        self.assertEqual(fs.normalize_league("ita.1"), "soccer/ita.1")

    def test_sport_esplicito(self):
        self.assertEqual(fs.normalize_league("basketball/nba"),
                         "basketball/nba")

    def test_sconosciuto(self):
        self.assertEqual(fs.normalize_league("xxx"), "")

    def test_league_names_default(self):
        self.assertIn("soccer/ita.1", fs.league_names(""))
        self.assertIn("basketball/nba", fs.league_names("nonsense"))

    def test_link_nba(self):
        self.assertEqual(fs.espn_link("basketball/nba", "9"),
                         "https://www.espn.com/basketball/game/_/gameId/9")


class TestMatching(unittest.TestCase):
    def test_fold_toglie_gli_accenti(self):
        self.assertEqual(fs.fold("Atlético"), "atletico")

    def test_parse_favorites(self):
        self.assertEqual(fs.parse_favorites("Inter, JUVENTUS ; milan"),
                         ["inter", "juventus", "milan"])

    def test_catalog_match(self):
        tokens = fs.favorite_tokens(["inter"])
        comps = [{"team": {"displayName": "Internazionale",
                           "abbreviation": "INT"}}]
        self.assertTrue(fs.is_favorite_match(comps, tokens))

    def test_no_match(self):
        tokens = fs.favorite_tokens(["napoli"])
        comps = [{"team": {"displayName": "Internazionale",
                           "abbreviation": "INT"}}]
        self.assertFalse(fs.is_favorite_match(comps, tokens))

    def test_free_token(self):
        # Id fuori catalogo usato come parola chiave.
        tokens = fs.favorite_tokens(["como"])
        comps = [{"team": {"displayName": "Como 1907", "abbreviation": "COM"}}]
        self.assertTrue(fs.is_favorite_match(comps, tokens))


class TestNormalize(unittest.TestCase):
    def test_live(self):
        m = fs.normalize_event("soccer/ita.1", fake_event())
        self.assertEqual(m["state"], "in")
        self.assertEqual(m["home"]["abbr"], "INT")
        self.assertEqual(m["home"]["id"], "110")
        self.assertEqual(m["away"]["score"], "1")
        self.assertEqual(m["clock"], "67'")
        self.assertTrue(m["home"]["logo"].endswith("INT.png"))
        self.assertIn("gameId/1", m["espnLink"])
        self.assertIn("/soccer/match/", m["espnLink"])

    def test_finished(self):
        m = fs.normalize_event("soccer/ita.1", fake_event(state="post", detail="FT"))
        self.assertEqual(m["state"], "post")
        self.assertEqual(m["detail"], "FT")


class TestSummary(unittest.TestCase):
    def test_stats_mapping(self):
        real = fs.http_get_json
        fs.http_get_json = lambda url: {
            "header": {"competitions": [{"id": "9",
                                         "competitors": [],
                                         "details": [
                                             {"clock": {"displayValue": "65'"},
                                              "scoringPlay": True,
                                              "redCard": False,
                                              "yellowCard": False,
                                              "penaltyKick": False,
                                              "participants": [{"athlete": {"displayName": "Tizio"}}],
                                              "team": {"abbreviation": "INT"}}]}]},
            "boxscore": {"teams": [
                {"homeAway": "home",
                 "statistics": [{"name": "possessionPct", "displayValue": "60"},
                                {"name": "yellowCards", "displayValue": "1"}]},
                {"homeAway": "away",
                 "statistics": [{"name": "possessionPct", "displayValue": "40"},
                                {"name": "yellowCards", "displayValue": "3"}]}]},
            "rosters": [
                {"homeAway": "home", "team": {"abbreviation": "INT"},
                 "roster": [{"starter": True, "jersey": "1",
                             "athlete": {"shortName": "M. Rossi",
                                         "displayName": "Mario Rossi"},
                             "position": {"abbreviation": "G"}}]},
                {"homeAway": "away", "team": {"abbreviation": "JUV"},
                 "roster": []}],
            "commentary": [
                {"time": {"displayValue": "65'"},
                 "text": "Gol di Tizio!"},
                {"time": {"displayValue": ""}, "text": "   "}],
            "news": {"articles": []}}
        try:
            out = fs.summary_payload("soccer/ita.1", "9")
        finally:
            fs.http_get_json = real
        poss = next(s for s in out["stats"] if s["label"] == "Possesso %")
        self.assertEqual((poss["home"], poss["away"]), ("60", "40"))
        # Rigche senza dati da nessuna parte spariscono (es. Parate).
        self.assertFalse([s for s in out["stats"] if s["label"] == "Parate"])
        self.assertEqual(len(out["timeline"]), 1)
        self.assertIn("Gol", out["timeline"][0]["text"])
        self.assertEqual(out["timeline"][0]["kind"], "goal")
        self.assertEqual(len(out["lineups"]), 2)
        self.assertEqual(out["lineups"][0]["players"][0]["name"], "M. Rossi")
        # La cronaca salta le righe vuote, più recente prima.
        self.assertEqual(len(out["commentary"]), 1)
        self.assertEqual(out["commentary"][0]["clock"], "65'")

    def test_teams_payload(self):
        real = fs.http_get_json
        fs.http_get_json = lambda url: {"sports": [{"leagues": [{"teams": [
            {"team": {"id": "103", "displayName": "AC Milan",
                      "abbreviation": "MIL", "shortDisplayName": "Milan",
                      "slug": "ac-milan", "location": "Milan",
                      "logos": [{"href": "https://x/103.png",
                                 "rel": ["full", "default"]},
                                {"href": "https://x/103-dark.png",
                                 "rel": ["full", "dark"]}]}}]}]}]}
        try:
            out = fs.teams_payload("soccer/ita.1")
        finally:
            fs.http_get_json = real
        self.assertEqual(len(out["teams"]), 1)
        team = out["teams"][0]
        self.assertEqual(team["id"], "103")
        self.assertEqual(team["logo"], "https://x/103.png")
        self.assertIn("milan", team["tokens"])
        self.assertIn("mil", team["tokens"])


if __name__ == "__main__":
    unittest.main()
