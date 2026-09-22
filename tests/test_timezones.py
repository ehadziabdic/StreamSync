import unittest
from datetime import datetime


class TestOffsetConversion(unittest.TestCase):
    def test_us_eastern_evening_is_next_day_utc(self):
        # Monday 21:00 US Eastern (EDT, -04:00) == Tuesday 01:00 UTC
        # == Tuesday ~03:00-04:00 in UTC+2/+3 -> must land on Tuesday.
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(
            parse_iso_date("2026-09-22T21:00:00-04:00"),
            datetime(2026, 9, 23, 1, 0, 0),
        )

    def test_anime_jst_offset_converts_to_utc(self):
        # 09:00 JST (+09:00) == 00:00 UTC same day.
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(
            parse_iso_date("2026-09-22T09:00:00+09:00"),
            datetime(2026, 9, 22, 0, 0, 0),
        )

    def test_zulu_unchanged(self):
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(
            parse_iso_date("2026-09-22T21:00:00Z"),
            datetime(2026, 9, 22, 21, 0, 0),
        )

    def test_naive_assumed_utc_as_before(self):
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(
            parse_iso_date("2026-09-22 21:00:00"),
            datetime(2026, 9, 22, 21, 0, 0),
        )

    def test_offset_with_millis(self):
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(
            parse_iso_date("2026-09-22T21:00:00.000-04:00"),
            datetime(2026, 9, 23, 1, 0, 0),
        )


class TestUserScenarioEndToEnd(unittest.TestCase):
    def test_us_monday_night_show_lands_on_tuesday_utc(self):
        # The user's scenario: a show airing Monday 21:00 US time must be
        # stored as Tuesday 01:00Z so a UTC+2 calendar shows Tuesday ~03:00.
        from simklCalendarExporter import generate_ics
        ev = {
            "title": "Late Show", "season": 1, "episode": 5, "ep_title": "",
            "date": "2026-09-22T21:00:00-04:00",
            "type": "shows", "ids": {"simkl:7"},
        }
        content, new_count, _ = generate_ics([ev])
        self.assertIn("DTSTART:20260923T010000Z", content)
        self.assertEqual(new_count, 1)


if __name__ == "__main__":
    unittest.main()
