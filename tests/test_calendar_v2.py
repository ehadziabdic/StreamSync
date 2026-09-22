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


if __name__ == "__main__":
    unittest.main()
