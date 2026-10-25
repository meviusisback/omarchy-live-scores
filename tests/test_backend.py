"""live-scores backend tests: fixtures only, no network."""
import os
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
    def test_bare_slug_becomes_soccer(self):
        self.assertEqual(fs.normalize_league("ita.1"), "soccer/ita.1")

    def test_explicit_sport(self):
        self.assertEqual(fs.normalize_league("basketball/nba"),
                         "basketball/nba")

    def test_unknown(self):
        self.assertEqual(fs.normalize_league("xxx"), "")

    def test_league_names_default(self):
        self.assertEqual(fs.league_names(""), [])
        self.assertEqual(fs.valid_leagues_or_empty("nonsense"), [])
        self.assertIn("soccer/ita.1", fs.valid_leagues_or_empty(""))
        self.assertIn("basketball/nba", fs.valid_leagues_or_empty(""))

    def test_link_nba(self):
        self.assertEqual(fs.espn_link("basketball/nba", "9"),
                         "https://www.espn.com/basketball/game/_/gameId/9")


class TestMatching(unittest.TestCase):
    def test_fold_strips_accents(self):
        self.assertEqual(fs.fold("Atlético"), "atletico")

    def test_parse_favorites(self):
        self.assertEqual(fs.parse_favorites("Inter, JUVENTUS ; milan"),
                         ["inter", "juventus", "milan"])

    def test_catalog_match(self):
        matchers = fs.favorite_matchers(["inter"])
        match = {"league": "soccer/ita.1",
                 "home": {"name": "Internazionale", "abbr": "INT"},
                 "away": {"name": "Juventus", "abbr": "JUV"}}
        self.assertTrue(fs.match_is_favorite(match, matchers))

    def test_no_match(self):
        matchers = fs.favorite_matchers(["napoli"])
        match = {"league": "soccer/ita.1",
                 "home": {"name": "Internazionale", "abbr": "INT"},
                 "away": {"name": "Juventus", "abbr": "JUV"}}
        self.assertFalse(fs.match_is_favorite(match, matchers))

    def test_free_token(self):
        # Off-catalog word used as a keyword.
        matchers = fs.favorite_matchers(["como"])
        match = {"league": "soccer/ita.1",
                 "home": {"name": "Como 1907", "abbr": "COM"},
                 "away": {"name": "Torino", "abbr": "TOR"}}
        self.assertTrue(fs.match_is_favorite(match, matchers))

    def test_int_does_not_match_saint(self):
        # "int" (Inter) is inside "saint" (Saint-Germain): whole words, no match.
        matchers = fs.favorite_matchers(["inter"])
        match = {"league": "soccer/fra.1",
                 "home": {"name": "Paris Saint-Germain", "abbr": "PSG"},
                 "away": {"name": "Olympique Lyonnais", "abbr": "OL"}}
        self.assertFalse(fs.match_is_favorite(match, matchers))

    def test_mil_does_not_match_milwaukee(self):
        # Same abbreviation, different sport: no NBA for Milan fans.
        matchers = fs.favorite_matchers(["milan"])
        match = {"league": "basketball/nba",
                 "home": {"name": "Milwaukee Bucks", "abbr": "MIL"},
                 "away": {"name": "Indiana Pacers", "abbr": "IND"}}
        self.assertFalse(fs.match_is_favorite(match, matchers))

    def test_direct_id(self):
        matchers = fs.favorite_matchers(["133730"])
        match = {"league": "basketball/nba",
                 "home": {"id": "133730", "name": "LA Lakers", "abbr": "LAL"},
                 "away": {"id": "5", "name": "Portland", "abbr": "POR"}}
        self.assertTrue(fs.match_is_favorite(match, matchers))


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
                 "text": "Tizio scores!"},
                 {"time": {"displayValue": ""}, "text": "   "}],
            "news": {"articles": []}}
        try:
            out = fs.summary_payload("soccer/ita.1", "9")
        finally:
            fs.http_get_json = real
        poss = next(s for s in out["stats"] if s["label"] == "Possession %")
        self.assertEqual((poss["home"], poss["away"]), ("60", "40"))
        # Rows with no data on either side disappear (e.g. Saves).
        self.assertFalse([s for s in out["stats"] if s["label"] == "Saves"])
        self.assertEqual(len(out["timeline"]), 1)
        self.assertIn("Goal", out["timeline"][0]["text"])
        self.assertEqual(out["timeline"][0]["kind"], "goal")
        self.assertEqual(len(out["lineups"]), 2)
        self.assertEqual(out["lineups"][0]["players"][0]["name"], "M. Rossi")
        # Commentary skips blank rows, most recent first.
        self.assertEqual(len(out["commentary"]), 1)
        self.assertEqual(out["commentary"][0]["clock"], "65'")

    def test_teams_payload(self):
        real = fs.http_get_json
        real_path = fs.teams_cache_path
        fs.http_get_json = lambda url: {"sports": [{"leagues": [{"teams": [
            {"team": {"id": "103", "displayName": "AC Milan",
                      "abbreviation": "MIL", "shortDisplayName": "Milan",
                      "slug": "ac-milan", "location": "Milan",
                      "logos": [{"href": "https://x/103.png",
                                 "rel": ["full", "default"]},
                                {"href": "https://x/103-dark.png",
                                 "rel": ["full", "dark"]}]}}]}]}]}
        fs.teams_cache_path = lambda: "/tmp/live-scores-test-teams.json"
        try:
            if os.path.exists("/tmp/live-scores-test-teams.json"):
                os.remove("/tmp/live-scores-test-teams.json")
            out = fs.teams_payload("soccer/ita.1")
        finally:
            fs.http_get_json = real
            fs.teams_cache_path = real_path
        self.assertEqual(len(out["teams"]), 1)
        team = out["teams"][0]
        self.assertEqual(team["id"], "103")
        self.assertEqual(team["logo"], "https://x/103.png")
        self.assertIn("milan", team["tokens"])
        self.assertIn("mil", team["tokens"])

    def test_national_team_aliases(self):
        self.assertIn("italia", fs.team_tokens({"displayName": "Italy"}))
        self.assertIn("francia", fs.team_tokens({"displayName": "France"}))
        self.assertNotIn("italia", fs.team_tokens({"displayName": "Inter"}))

    def test_hostile_league_names(self):
        # 50 junk entries + separators: no valid league → [].
        junk = ";".join("zzz%d" % i for i in range(50))
        self.assertEqual(fs.league_names(junk), [])
        self.assertEqual(fs.valid_leagues_or_empty(junk), [])
        # Empty string = default (all), not an error.
        self.assertIn("soccer/ita.1", fs.valid_leagues_or_empty(""))
        # Path traversal discarded.
        self.assertNotIn("../../etc", fs.league_names("../../etc,soccer/ita.1"))
        self.assertIn("soccer/ita.1", fs.league_names("../../etc,soccer/ita.1"))

    def test_scoreboard_invalid_leagues(self):
        out = fs.scoreboard_payload("inter", "spazzatura")
        self.assertEqual(out["live"], [])
        self.assertEqual(out["error"], "no-valid-leagues")

    def test_merge_corrupt_cache(self):
        real_path = fs.teams_cache_path
        fs.teams_cache_path = lambda: "/tmp/live-scores-test-corrupt.json"
        try:
            with open("/tmp/live-scores-test-corrupt.json", "w") as fh:
                fh.write('[1, "x", null]')
            merged = fs.merge_teams_cache(["soccer/ita.1"], [])
            self.assertEqual(merged, [])
        finally:
            fs.teams_cache_path = real_path

    def test_http_retry(self):
        # urlopen fails twice then succeeds: http_get_json must retry.
        real_urlopen = fs.urllib.request.urlopen
        calls = {"n": 0}

        class FakeResp:
            def read(self):
                return b'{"ok": true}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def flaky(req, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise fs.urllib.request.HTTPError(
                    req.full_url, 500, "boom", None, None)
            return FakeResp()

        fs.urllib.request.urlopen = flaky
        try:
            self.assertEqual(fs.http_get_json("https://x.test/y"), {"ok": True})
        finally:
            fs.urllib.request.urlopen = real_urlopen
        self.assertEqual(calls["n"], 3)


if __name__ == "__main__":
    unittest.main()
