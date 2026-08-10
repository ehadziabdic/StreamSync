import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

# ==========================================
# SECRETS & ENVIRONMENT VARIABLES
# ==========================================
SIMKL_CLIENT_ID = os.environ.get("SIMKL_CLIENT_ID")
SIMKL_ACCESS_TOKEN = os.environ.get("SIMKL_ACCESS_TOKEN")
GIST_ID = os.environ.get("GIST_ID")
GH_TOKEN = os.environ.get("GH_PAT_TOKEN") or os.environ.get("GIST_TOKEN")
# ==========================================


def safe_int(val, default=1):
    """Safely convert season/episode values to integers."""
    if isinstance(val, dict):
        val = val.get("number") or val.get("season") or val.get("episode")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def fetch_json(url, headers=None):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "SimklCalendarExporter/4.0"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def clean_string(text):
    """Normalize text for exact title matching."""
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def extract_all_ids(obj):
    """Extract all valid Simkl, TVDB, IMDb, and TMDB IDs."""
    ids = set()
    if not isinstance(obj, dict):
        return ids

    targets = [
        obj,
        obj.get("show"),
        obj.get("anime"),
        obj.get("movie"),
        obj.get("ids"),
    ]
    for t in targets:
        if isinstance(t, dict):
            for k in [
                "simkl",
                "simkl_id",
                "tvdb",
                "tvdb_id",
                "imdb",
                "tmdb",
                "mal",
            ]:
                val = t.get(k)
                if val is not None and str(val).strip() not in (
                    "",
                    "0",
                    "None",
                    "null",
                ):
                    ids.add(str(val))

            ids_dict = t.get("ids")
            if isinstance(ids_dict, dict):
                for val in ids_dict.values():
                    if val is not None and str(val).strip() not in (
                        "",
                        "0",
                        "None",
                        "null",
                    ):
                        ids.add(str(val))
    return ids


def get_user_watchlist():
    """Fetch active watchlist items (watching / plantowatch only)."""
    headers = {
        "Authorization": f"Bearer {SIMKL_ACCESS_TOKEN}",
        "simkl-api-key": SIMKL_CLIENT_ID,
    }

    user_ids = set()
    user_titles = set()
    direct_events = []

    # Valid active statuses to include
    ALLOWED_STATUSES = {"watching", "plantowatch", "plan to watch", "hold"}

    for category in ["shows", "anime", "movies"]:
        url = f"https://api.simkl.com/sync/all-items/{category}?next_watch_info=yes"
        print(f"[*] Fetching watchlist for: {category}...")
        data = fetch_json(url, headers=headers)

        if not data:
            continue

        items = (
            data.get(category, [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )

        active_count = 0
        for item in items:
            status = str(item.get("status", "")).lower()

            # Skip dropped, completed, or unlisted items
            if status not in ALLOWED_STATUSES:
                continue

            active_count += 1
            show_obj = (
                item.get("show")
                or item.get("anime")
                or item.get("movie")
                or item
            )

            extracted_ids = extract_all_ids(show_obj)
            user_ids.update(extracted_ids)

            raw_title = show_obj.get("title", "")
            cleaned = clean_string(raw_title)
            if cleaned:
                user_titles.add(cleaned)

            next_info = item.get("next_to_watch_info")
            if next_info and isinstance(next_info, dict):
                ep_date = next_info.get("date") or next_info.get("release_date")
                if ep_date:
                    direct_events.append(
                        {
                            "title": raw_title or "Title",
                            "season": (
                                safe_int(next_info.get("season"), 1)
                                if category != "movies"
                                else None
                            ),
                            "episode": (
                                safe_int(next_info.get("episode"), 1)
                                if category != "movies"
                                else None
                            ),
                            "ep_title": next_info.get("title", ""),
                            "date": ep_date,
                            "type": category,
                        }
                    )

        print(f"    Found {active_count} active items in {category}.")

    return user_ids, user_titles, direct_events


def get_calendar_events(user_ids, user_titles):
    """Scan calendar feeds for active watchlist shows and movies."""
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month

    next_month_dt = (now.replace(day=28) + timedelta(days=4)).replace(day=1)

    calendar_urls = [
        ("https://data.simkl.in/calendar/tv.json", "shows"),
        ("https://data.simkl.in/calendar/anime.json", "anime"),
        ("https://data.simkl.in/calendar/movies.json", "movies"),
        (
            f"https://data.simkl.in/calendar/{current_year}/{current_month}/tv.json",
            "shows",
        ),
        (
            f"https://data.simkl.in/calendar/{current_year}/{current_month}/anime.json",
            "anime",
        ),
        (
            f"https://data.simkl.in/calendar/{current_year}/{current_month}/movies.json",
            "movies",
        ),
        (
            f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/tv.json",
            "shows",
        ),
        (
            f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/anime.json",
            "anime",
        ),
        (
            f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/movies.json",
            "movies",
        ),
    ]

    matched_events = []

    for url, category in calendar_urls:
        print(f"[*] Scanning feed: {url}...")
        feed = fetch_json(url)
        if not feed or not isinstance(feed, list):
            continue

        feed_matches = 0
        for entry in feed:
            entry_ids = extract_all_ids(entry)

            show_obj = (
                entry.get("show")
                if isinstance(entry.get("show"), dict)
                else {}
            )
            entry_title = (
                entry.get("show_title")
                or entry.get("anime_title")
                or entry.get("movie_title")
                or show_obj.get("title")
                or entry.get("title", "")
            )
            cleaned_entry_title = clean_string(entry_title)

            id_match = bool(entry_ids & user_ids)
            title_match = (
                cleaned_entry_title in user_titles
                if cleaned_entry_title
                else False
            )

            if id_match or title_match:
                feed_matches += 1
                matched_events.append(
                    {
                        "title": entry_title or "Title",
                        "season": (
                            safe_int(entry.get("season"), 1)
                            if category != "movies"
                            else None
                        ),
                        "episode": (
                            safe_int(entry.get("episode"), 1)
                            if category != "movies"
                            else None
                        ),
                        "ep_title": entry.get("episode_title")
                        or entry.get("title", ""),
                        "date": entry.get("date")
                        or entry.get("air_date")
                        or entry.get("release_date"),
                        "type": category,
                    }
                )

        print(f"    Matched {feed_matches} entries.")

    return matched_events


def parse_iso_date(date_str):
    if not date_str:
        return None
    clean_str = (
        str(date_str)
        .replace("Z", "")
        .replace("T", " ")
        .split("+")[0]
        .split(".")[0]
    )
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    return None


def generate_ics(events):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Simkl Calendar Exporter//EN",
        "X-WR-CALNAME:Simkl TV Calendar",
        "X-WR-TIMEZONE:UTC",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    seen_time_slots = set()
    now_cutoff = datetime.utcnow() - timedelta(days=1)

    for ev in events:
        dt_start = parse_iso_date(ev.get("date"))
        if not dt_start:
            continue

        # Filter out past events aired before yesterday
        if dt_start < now_cutoff:
            continue

        dt_end = dt_start + timedelta(minutes=45)

        # Build summary and deduplication key based on show type
        is_movie = ev.get("type") == "movies" or (
            ev.get("season") is None and ev.get("episode") is None
        )

        if is_movie:
            summary = f"{ev['title']}"
            dedup_key = (
                f"movie-{dt_start.strftime('%Y%m%d%H%M')}-{clean_string(ev['title'])[:10]}"
            )
        else:
            season = safe_int(ev.get("season"), 1)
            episode = safe_int(ev.get("episode"), 1)
            ep_code = f"S{season:02d}E{episode:02d}"
            summary = f"{ev['title']} {ep_code}"
            # Deduplicate alternate English/Japanese title variations sharing time + S/E numbers
            dedup_key = f"tv-{dt_start.strftime('%Y%m%d%H%M')}-s{season:02d}e{episode:02d}"

        if dedup_key in seen_time_slots:
            continue
        seen_time_slots.add(dedup_key)

        description = (
            ev["ep_title"] if ev.get("ep_title") else f"Release: {ev['title']}"
        )
        uid_str = clean_string(f"{summary}-{dt_start.strftime('%Y%m%d%H%M')}")

        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        str_start = dt_start.strftime("%Y%m%dT%H%M%SZ")
        str_end = dt_end.strftime("%Y%m%dT%H%M%SZ")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid_str}@simkl",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{str_start}",
                f"DTEND:{str_end}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\n".join(lines), len(seen_time_slots)


def update_gist(ics_content):
    """Publish generated .ics content directly to GitHub Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SimklCalendarExporter/4.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = json.dumps(
        {
            "description": "Updated Simkl TV Calendar",
            "files": {"trakt.ics": {"content": ics_content}},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload, headers=headers, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("\n✅ SUCCESS: trakt.ics updated in GitHub Gist!")
            else:
                print(f"\n❌ Failed to update Gist. Status code: {response.status}")
    except Exception as e:
        print(f"\n❌ Error updating Gist: {e}")


def main():
    missing = [
        var
        for var, val in [
            ("SIMKL_CLIENT_ID", SIMKL_CLIENT_ID),
            ("SIMKL_ACCESS_TOKEN", SIMKL_ACCESS_TOKEN),
            ("GIST_ID", GIST_ID),
            ("GH_PAT_TOKEN / GIST_TOKEN", GH_TOKEN),
        ]
        if not val
    ]

    if missing:
        print(f"❌ ERROR: Missing required GitHub Secrets: {', '.join(missing)}")
        exit(1)

    user_ids, user_titles, direct_events = get_user_watchlist()
    calendar_events = get_calendar_events(user_ids, user_titles)

    all_events = direct_events + calendar_events
    ics_content, event_count = generate_ics(all_events)

    print(f"\n[+] Generated calendar with {event_count} active upcoming events.")
    update_gist(ics_content)


if __name__ == "__main__":
    main()
