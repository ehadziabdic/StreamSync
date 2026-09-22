import unittest
from datetime import datetime, timedelta


def _vevent(uid, dtstart, summary="Show S01E01", status=None, dtend=None, seq=None):
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTART:{dtstart}"]
    if dtend:
        lines.append(f"DTEND:{dtend}")
    lines.append(f"SUMMARY:{summary}")
    if status:
        lines.append(f"STATUS:{status}")
    if seq is not None:
        lines.append(f"SEQUENCE:{seq}")
    lines.append("END:VEVENT")
    return "\n".join(lines)


def _ics(*events):
    return "\n".join(
        ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Simkl Calendar Exporter//EN"]
        + list(events)
        + ["END:VCALENDAR"]
    )


OLD_AIRED = _vevent("tv-simkl:1-s01e01@simkl", "20260901T040000Z", dtend="20260901T044500Z")
OLD_FUTURE = _vevent("tv-simkl:1-s01e02@simkl", "20260928T040000Z", dtend="20260928T044500Z")
OLD_CANCELLED = _vevent(
    "tv-simkl:2-s01e01@simkl", "20260820T040000Z", dtend="20260820T044500Z",
    status="CANCELLED", seq=1,
)
OLD_ANCIENT = _vevent("tv-simkl:3-s01e01@simkl", "20250101T040000Z", dtend="20250101T044500Z")

NOW = datetime(2026, 9, 22)


class TestParseIsoBasicFormat(unittest.TestCase):
    def test_parses_ics_basic_utc_format(self):
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(parse_iso_date("20260720T040000Z"), datetime(2026, 7, 20, 4, 0, 0))

    def test_existing_iso_format_still_works(self):
        from simklCalendarExporter import parse_iso_date
        self.assertEqual(parse_iso_date("2026-07-20T04:00:00Z"), datetime(2026, 7, 20, 4, 0, 0))


class TestParseIcsEvents(unittest.TestCase):
    def test_extracts_uid_dtstart_status(self):
        from simklCalendarExporter import parse_ics_events
        events = parse_ics_events(_ics(OLD_AIRED, OLD_CANCELLED))
        by_uid = {e["UID"]: e for e in events}
        self.assertEqual(by_uid["tv-simkl:1-s01e01@simkl"]["DTSTART"], "20260901T040000Z")
        self.assertEqual(by_uid["tv-simkl:1-s01e01@simkl"]["DTEND"], "20260901T044500Z")
        self.assertEqual(by_uid["tv-simkl:2-s01e01@simkl"]["STATUS"], "CANCELLED")

    def test_unfolds_folded_lines(self):
        from simklCalendarExporter import parse_ics_events
        folded = "BEGIN:VEVENT\nUID:x@simkl\nSUMMARY:A very long summary that\n continues here\nEND:VEVENT"
        events = parse_ics_events(_ics(folded))
        self.assertEqual(events[0]["SUMMARY"], "A very long summary thatcontinues here")

    def test_skips_blocks_without_uid(self):
        from simklCalendarExporter import parse_ics_events
        events = parse_ics_events(_ics("BEGIN:VEVENT\nSUMMARY:No uid\nEND:VEVENT"))
        self.assertEqual(events, [])

    def test_empty_text_returns_empty(self):
        from simklCalendarExporter import parse_ics_events
        self.assertEqual(parse_ics_events(""), [])
        self.assertEqual(parse_ics_events("not a calendar"), [])


class TestBuildCancellations(unittest.TestCase):
    def test_aired_and_gone_is_cancelled(self):
        from simklCalendarExporter import build_cancellations
        out = build_cancellations(_ics(OLD_AIRED, OLD_FUTURE), {"other-uid"}, now=NOW)
        by_uid = {c["uid"]: c for c in out}
        self.assertIn("tv-simkl:1-s01e01@simkl", by_uid)
        self.assertEqual(by_uid["tv-simkl:1-s01e01@simkl"]["dtstart"], "20260901T040000Z")

    def test_still_present_uid_is_not_cancelled(self):
        from simklCalendarExporter import build_cancellations
        out = build_cancellations(
            _ics(OLD_AIRED, OLD_FUTURE), {"tv-simkl:1-s01e01@simkl"}, now=NOW
        )
        self.assertEqual([c["uid"] for c in out], [])

    def test_old_cancellation_within_window_is_carried(self):
        from simklCalendarExporter import build_cancellations
        out = build_cancellations(_ics(OLD_CANCELLED), set(), now=NOW)
        self.assertEqual([c["uid"] for c in out], ["tv-simkl:2-s01e01@simkl"])

    def test_ancient_aired_event_is_pruned(self):
        from simklCalendarExporter import build_cancellations
        out = build_cancellations(_ics(OLD_ANCIENT), set(), now=NOW)
        self.assertEqual(out, [])

    def test_unparsable_dtstart_is_skipped(self):
        from simklCalendarExporter import build_cancellations
        bad = _vevent("x@simkl", "not-a-date")
        out = build_cancellations(_ics(bad), set(), now=NOW)
        self.assertEqual(out, [])

    def test_empty_previous_returns_empty(self):
        from simklCalendarExporter import build_cancellations
        self.assertEqual(build_cancellations("", set(), now=NOW), [])


class TestFetchPreviousIcsWithoutCreds(unittest.TestCase):
    def test_returns_empty_without_gist_config(self):
        import os
        self.assertFalse(os.environ.get("GIST_ID"))
        from simklCalendarExporter import fetch_previous_ics
        self.assertEqual(fetch_previous_ics(), "")


class TestGenerateIcsWithCancellations(unittest.TestCase):
    def test_new_events_carry_sequence_zero(self):
        from simklCalendarExporter import generate_ics
        ev = {
            "title": "Future Show", "season": 1, "episode": 1, "ep_title": "",
            "date": (NOW + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "type": "shows", "ids": {"simkl:9"},
        }
        content, new_count, cancelled_count = generate_ics([ev])
        self.assertIn("SEQUENCE:0", content)
        self.assertEqual((new_count, cancelled_count), (1, 0))

    def test_cancelled_blocks_appended_with_status_and_sequence(self):
        from simklCalendarExporter import generate_ics
        cancelled = [{
            "uid": "tv-simkl:1-s01e01@simkl",
            "dtstart": "20260901T040000Z",
            "dtend": "20260901T044500Z",
            "summary": "Show S01E01",
        }]
        content, new_count, cancelled_count = generate_ics([], cancelled=cancelled)
        self.assertIn("STATUS:CANCELLED", content)
        self.assertIn("SEQUENCE:1", content)
        self.assertIn("UID:tv-simkl:1-s01e01@simkl", content)
        self.assertTrue(content.rstrip().endswith("END:VCALENDAR"))
        self.assertEqual((new_count, cancelled_count), (0, 1))


if __name__ == "__main__":
    unittest.main()
