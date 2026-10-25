"""Test del backend live-scores: solo dati finti, niente rete."""
import sys
import unittest

sys.path.insert(0, "..")
import fetch_scores as fs


def fake_comp(name, abbr, score, home_away):
    return {"homeAway": home_away, "score": score,
            "team": {"displayName": name, "abbreviation": abbr,
                     "logo": "https://x/{}.png".format(abbr)}}


def fake_event(eid="1", state="in", clock="67'", detail="2nd Half - 67'"):
    return {"id": eid, "date": "2026-10-25T18:00Z",
            "status": {"displayClock": clock,
                       "type": {"state": state, "shortDetail": detail,
                                "detail": detail}},
            "competitions": [{"competitors": [
                fake_comp("Internazionale", "INT", "2", "home"),
                fake_comp("Juventus", "JUV", "1", "away")]}]}


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
        m = fs.normalize_event("ita.1", fake_event())
        self.assertEqual(m["state"], "in")
        self.assertEqual(m["home"]["abbr"], "INT")
        self.assertEqual(m["away"]["score"], "1")
        self.assertEqual(m["clock"], "67'")
        self.assertTrue(m["home"]["logo"].endswith("INT.png"))
        self.assertIn("gameId/1", m["espnLink"])

    def test_finished(self):
        m = fs.normalize_event("ita.1", fake_event(state="post", detail="FT"))
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
            "news": {"articles": []}}
        try:
            out = fs.summary_payload("ita.1", "9")
        finally:
            fs.http_get_json = real
        poss = next(s for s in out["stats"] if s["label"] == "Possesso %")
        self.assertEqual((poss["home"], poss["away"]), ("60", "40"))
        self.assertEqual(len(out["timeline"]), 1)
        self.assertIn("Gol", out["timeline"][0]["text"])
        self.assertEqual(out["timeline"][0]["kind"], "goal")


if __name__ == "__main__":
    unittest.main()
