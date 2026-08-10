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
    """Safely convert season/episode values to integers, even if returned as a dict."""
    if isinstance(val, dict):
        val = val.get("number") or val.get("season") or val.get("episode")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def fetch_json(url, headers=None):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "SimklCalendarExporter/3.0"

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
    """Extract all valid Simkl, TVDB, IMDb, and TMDB IDs from any object structure."""
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
    """Fetch active shows, anime, and movies watchlist from Simkl Sync API."""
    headers = {
        "Authorization": f"Bearer {SIMKL_ACCESS_TOKEN}",
        "simkl-api-key": SIMKL_CLIENT_ID,
    }

    user_ids = set()
    user_titles = set()
    direct_events = []

    # Check shows, anime, and movies
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
        print(f"    Found {len(items)} items in {category}.")

        for item in items:
            # Filter out dropped or completed items
            status = str(item.get("status", "")).lower()
            if status in ["dropped", "completed"]:
                continue

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

            # Direct release or episode info attached to watchlist
            next_info = item.get("next_to_watch_info")
            if next_info and isinstance(next_info, dict):
                ep_date = next_info.get("date") or next_info.get("release_date")
                if ep_date:
                    direct_events.append(
                        {
                            "title": raw_title or "Title",
                            "season": safe_int(next_info.get("season"), 1),
                            "episode": safe_int(next_info.get("episode"), 1),
                            "ep_title": next_info.get("title", ""),
                            "date": ep_date,
                        }
                    )

    return user_ids, user_titles, direct_events


def get_calendar_events(user_ids, user_titles):
    """Scan rolling and monthly calendar feeds for active watchlist items."""
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month

    next_month_dt = (now.replace(day=28) + timedelta(days=4)).replace(day=1)

    calendar_urls = [
        "https://data.simkl.in/calendar/tv.json",
        "https://data.simkl.in/calendar/anime.json",
        "https://data.simkl.in/calendar/movies.json",
        f"https://data.simkl.in/calendar/{current_year}/{current_month}/tv.json",
        f"https://data.simkl.in/calendar/{current_year}/{current_month}/anime.json",
        f"https://data.simkl.in/calendar/{current_year}/{current_month}/movies.json",
        f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/tv.json",
        f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/anime.json",
        f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/movies.json",
    ]

    matched_events = []

    for url in calendar_urls:
        print(f"[*] Scanning feed: {url}...")
        feed = fetch_json(url)
        if not feed or not isinstance(feed, list):
            continue

        feed_matches = 0
        for entry in feed:
            entry_ids = extract_all_ids(entry)

            # Prioritize show/movie title over episode title
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

            # Match by ID or exact show title
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
                        "season": safe_int(entry.get("season"), 1),
                        "episode": safe_int(entry.get("episode"), 1),
                        "ep_title": entry.get("episode_title")
                        or entry.get("title", ""),
                        "date": entry.get("date")
                        or entry.get("air_date")
                        or entry.get("release_date"),
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

    seen_uids = set()

    for ev in events:
        dt_start = parse_iso_date(ev.get("date"))
        if not dt_start:
            continue

        dt_end = dt_start + timedelta(minutes=45)

        season = safe_int(ev.get("season"), 1)
        episode = safe_int(ev.get("episode"), 1)
        ep_code = f"S{season:02d}E{episode:02d}"

        summary = f"{ev['title']} {ep_code}"
        description = (
            ev["ep_title"] if ev.get("ep_title") else f"Episode {ep_code}"
        )

        uid_raw = clean_string(
            f"{ev['title']}-{ep_code}-{dt_start.strftime('%Y%m%d%H%M')}"
        )
        if uid_raw in seen_uids:
            continue
        seen_uids.add(uid_raw)

        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        str_start = dt_start.strftime("%Y%m%dT%H%M%SZ")
        str_end = dt_end.strftime("%Y%m%dT%H%M%SZ")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid_raw}@simkl",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{str_start}",
                f"DTEND:{str_end}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\n".join(lines), len(seen_uids)


def update_gist(ics_content):
    """Publish generated .ics content directly to your GitHub Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SimklCalendarExporter/3.0",
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

    print(f"\n[+] Generated calendar with {event_count} total upcoming events.")
    update_gist(ics_content)


if __name__ == "__main__":
    main()
