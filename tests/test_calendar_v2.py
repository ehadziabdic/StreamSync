import unittest

V1_FEED_SAMPLE = [
    {
        "show_title": "King of the Hill",
        "season": 15, "episode": 1,
        "date": "2026-07-20T04:00:00Z",
        "show": {"title": "King of the Hill", "ids": {"simkl": 3437, "tvdb": 73141, "imdb": "tt0118375", "tmdb": "1434"}},
        "episode_title": "Failure to Hard Launch",
    }
]

V2_FILE_SAMPLE = {
    "calendar": [
        {"simkl_id": 3437, "date": "2026-07-20T04:00:00Z", "finale_type": None,
         "episode": {"season": 15, "episode": 1, "title": "Failure to Hard Launch", "url": "https://simkl.com/tv/3437/x/season-15/episode-1/"}}
    ],
    "metadata": {
        "3437": {"title": "King of the Hill", "url": "/tv/3437/king-of-the-hill",
                 "poster": "12/12634613c2b41dc5a1",
                 "ids": {"simkl_id": 3437, "slug": "king-of-the-hill", "imdb": "tt0118375", "tmdb": "1434", "tvdb": "73141"},
                 "ratings": {"simkl": {"rating": 8.1, "votes": 942}}}
    },
}

USER_IDS_SAMPLE = {"shows": {"simkl:3437", "tvdb:73141"}, "anime": set(), "movies": set()}
USER_TITLES_SAMPLE = {"shows": {"kingofthehill"}, "anime": set(), "movies": set()}


class TestShapeDispatch(unittest.TestCase):
    def test_detects_v1_list_vs_v2_dict(self):
        from simklCalendarExporter import detect_feed_shape
        self.assertEqual(detect_feed_shape(V1_FEED_SAMPLE), "v1")
        self.assertEqual(detect_feed_shape(V2_FILE_SAMPLE), "v2")


class TestCalendarUrl(unittest.TestCase):
    def test_builds_v2_url_with_required_params(self):
        import os
        os.environ["SIMKL_CLIENT_ID"] = "TESTID"
        from simklCalendarExporter import build_calendar_url
        url = build_calendar_url("/calendar/v2/tv.json")
        self.assertIn("https://data.simkl.in/calendar/v2/tv.json?", url)
        self.assertIn("client_id=TESTID", url)
        self.assertIn("app-name=", url)
        self.assertIn("app-version=", url)

    def test_fetch_sends_user_agent(self):
        from simklCalendarExporter import fetch_json
        import urllib.request
        seen = {}
        real = urllib.request.Request
        class Spy(real):
            def __init__(self, url, headers=None, **kw):
                seen.update(headers or {})
                super().__init__(url, headers=headers, **kw)
        urllib.request.Request = Spy
        try:
            fetch_json("https://data.simkl.in/calendar/v2/tv.json?client_id=x&app-name=a&app-version=b")
        except Exception:
            pass
        finally:
            urllib.request.Request = real
        self.assertIn("User-Agent", seen)


class TestNormalizeV2(unittest.TestCase):
    def test_tv_join_enriches_ids_and_title(self):
        from simklCalendarExporter import normalize_v2_entry
        cal = V2_FILE_SAMPLE["calendar"][0]
        meta = V2_FILE_SAMPLE["metadata"]["3437"]
        ev = normalize_v2_entry(cal, meta, "shows")
        self.assertEqual(ev["title"], "King of the Hill")
        self.assertEqual((ev["season"], ev["episode"]), (15, 1))
        self.assertEqual(ev["ep_title"], "Failure to Hard Launch")
        self.assertEqual(ev["date"], "2026-07-20T04:00:00Z")
        self.assertIn("simkl:3437", ev["ids"])
        self.assertIn("tvdb:73141", ev["ids"])

    def test_anime_missing_season_defaults_to_1(self):
        from simklCalendarExporter import normalize_v2_entry
        cal = {"simkl_id": 1, "date": "2026-07-20T00:00:00Z", "finale_type": None,
               "episode": {"episode": 148, "title": "Ep 148", "url": "https://simkl.com/x"}}
        meta = {"title": "Chibi Maruko-chan", "ids": {"simkl_id": 1}}
        ev = normalize_v2_entry(cal, meta, "anime")
        self.assertEqual(ev["season"], 1)
        self.assertEqual(ev["episode"], 148)

    def test_movie_has_no_episode_object(self):
        from simklCalendarExporter import normalize_v2_entry
        cal = {"simkl_id": 53536, "date": "2026-12-18T00:00:00Z", "finale_type": None}
        meta = {"title": "Ghost in the Shell", "ids": {"simkl_id": 53536, "imdb": "tt0113568"}}
        ev = normalize_v2_entry(cal, meta, "movies")
        self.assertIsNone(ev["season"])
        self.assertIsNone(ev["episode"])
        self.assertIn("simkl:53536", ev["ids"])

    def test_sparse_tv_record_does_not_crash(self):
        from simklCalendarExporter import normalize_v2_entry
        cal = {"simkl_id": 999, "date": "2026-07-20T00:00:00Z", "finale_type": None,
               "episode": {"season": 1, "episode": 1, "title": None, "url": ""}}
        meta = {"title": "New Show", "url": "/tv/999/x", "poster": None,
                "ids": {"simkl_id": 999, "slug": "x"}}
        ev = normalize_v2_entry(cal, meta, "shows")
        self.assertEqual(ev["title"], "New Show")


class TestCalendarMatching(unittest.TestCase):
    def test_v2_entry_matches_on_id(self):
        from simklCalendarExporter import match_normalized_event
        ev = {"title": "King of the Hill", "season": 15, "episode": 1,
              "ep_title": "x", "date": "2026-07-20T04:00:00Z", "type": "shows",
              "ids": {"simkl:3437"}, "_alt_titles": []}
        self.assertTrue(match_normalized_event(ev, USER_IDS_SAMPLE, USER_TITLES_SAMPLE))

    def test_v2_entry_without_match_returns_false(self):
        from simklCalendarExporter import match_normalized_event
        ev = {"title": "Some Unknown Show", "season": 1, "episode": 1,
              "ep_title": "", "date": "2026-07-20T04:00:00Z", "type": "shows",
              "ids": {"simkl:99999"}, "_alt_titles": ["Some Unknown Alt"]}
        self.assertFalse(match_normalized_event(ev, USER_IDS_SAMPLE, USER_TITLES_SAMPLE))

    def test_v2_entry_matches_on_alt_title(self):
        from simklCalendarExporter import match_normalized_event
        ev = {"title": "König von Texas", "season": 15, "episode": 1,
              "ep_title": "", "date": "2026-07-20T04:00:00Z", "type": "shows",
              "ids": {"simkl:99999"}, "_alt_titles": ["King of the Hill"]}
        self.assertTrue(match_normalized_event(ev, USER_IDS_SAMPLE, USER_TITLES_SAMPLE))


if __name__ == "__main__":
    unittest.main()
