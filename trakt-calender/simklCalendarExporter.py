from datetime import datetime, timedelta
import json
import os
import urllib.request

# ==========================================
# CONFIGURATION
# ==========================================
SIMKL_CLIENT_ID = "24f203f7e590f4cc9fb9813291ca278c9c9caced016536314f3fe24dd00d7b8f"  # Replace with your Simkl API Client ID
SIMKL_ACCESS_TOKEN = (
    "9d9396b283276f309b98ea67f4dcfdf8f371229d45a11363e0bd74f837c60bdc"  # Replace with your User Access Token
)
OUTPUT_FILENAME = "simkl_tv_calendar.ics"
# ==========================================


def fetch_json(url, headers=None):
    """Utility function to make HTTP GET requests and parse JSON."""
    if headers is None:
        headers = {}
    headers["User-Agent"] = "SimklCalendarExporter/1.0"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[!] Error fetching {url}: {e}")
        return None


def extract_simkl_ids(item):
    """Safely extract simkl ID as an integer from various item formats."""
    if not isinstance(item, dict):
        return None

    # Handle wrapped structures: {"show": {"ids": ...}} or {"ids": ...}
    target = item.get("show") or item.get("anime") or item
    ids = target.get("ids", {})

    simkl_id = ids.get("simkl")
    if simkl_id is not None:
        try:
            return int(simkl_id)
        except (ValueError, TypeError):
            pass
    return None


def get_user_watchlist():
    """Fetch user shows and anime watchlist from Simkl Sync API."""
    headers = {
        "Authorization": f"Bearer {SIMKL_ACCESS_TOKEN}",
        "simkl-api-key": SIMKL_CLIENT_ID,
    }

    watchlist_ids = set()
    direct_events = []

    # Fetch both shows and anime watchlists
    categories = ["shows", "anime"]

    for category in categories:
        url = f"https://api.simkl.com/sync/all-items/{category}?next_watch_info=yes"
        print(f"[*] Fetching user watchlist for: {category}...")
        data = fetch_json(url, headers=headers)

        if not data:
            continue

        # Unnest items list from wrapper key if present
        items = (
            data.get(category, [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        print(f"    Found {len(items)} items in {category} watchlist.")

        for item in items:
            sid = extract_simkl_ids(item)
            if sid:
                watchlist_ids.add(sid)

            # Check if Simkl directly returned 'next_to_watch_info'
            next_info = item.get("next_to_watch_info")
            if next_info and isinstance(next_info, dict):
                show_obj = item.get("show") or item.get("anime") or {}
                title = show_obj.get("title", "TV Show")
                ep_date = next_info.get("date")
                season = next_info.get("season", 1)
                episode = next_info.get("episode", 1)
                ep_title = next_info.get("title", "")

                if ep_date:
                    direct_events.append(
                        {
                            "title": title,
                            "season": season,
                            "episode": episode,
                            "ep_title": ep_title,
                            "date": ep_date,
                            "simkl_id": sid,
                        }
                    )

    return watchlist_ids, direct_events


def get_global_calendar_events(watchlist_ids):
    """Fetch global Simkl 33-day calendar feeds and filter by user watchlist."""
    calendar_urls = [
        "https://data.simkl.in/calendar/tv.json",
        "https://data.simkl.in/calendar/anime.json",
    ]

    calendar_events = []

    for url in calendar_urls:
        print(f"[*] Fetching global calendar feed from {url}...")
        feed = fetch_json(url)
        if not feed or not isinstance(feed, list):
            continue

        matched_count = 0
        for entry in feed:
            sid = extract_simkl_ids(entry)
            if sid in watchlist_ids:
                matched_count += 1
                calendar_events.append(
                    {
                        "title": entry.get("title", "TV Show"),
                        "season": entry.get("season", 1),
                        "episode": entry.get("episode", 1),
                        "ep_title": entry.get("episode_title")
                        or entry.get("title", ""),
                        "date": entry.get("date"),
                        "simkl_id": sid,
                    }
                )
        print(f"    Matched {matched_count} upcoming episodes.")

    return calendar_events


def parse_iso_date(date_str):
    """Parse ISO date string into a datetime object."""
    if not date_str:
        return None
    # Strip fractional seconds/timezones if needed for simple parsing
    clean_str = (
        date_str.replace("Z", "+00:00")
        .replace(" ", "T")
        .split("+")[0]
        .split(".")[0]
    )
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    return None


def generate_ics(events, filename):
    """Generate .ics file from gathered episode events."""
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

        s_str = f"S{ev['season']:02d}" if ev.get("season") else ""
        e_str = f"E{ev['episode']:02d}" if ev.get("episode") else ""
        ep_code = f"{s_str}{e_str}".strip()

        summary = (
            f"{ev['title']} {ep_code}".strip()
            if ep_code
            else f"{ev['title']}"
        )
        description = (
            f"{ev['ep_title']}"
            if ev.get("ep_title")
            else f"New episode of {ev['title']}"
        )

        uid = f"simkl-{ev.get('simkl_id', '0')}-{ep_code}-{dt_start.strftime('%Y%m%d%H%M')}@simkl"

        if uid in seen_uids:
            continue
        seen_uids.add(uid)

        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        str_start = dt_start.strftime("%Y%m%dT%H%M%SZ")
        str_end = dt_end.strftime("%Y%m%dT%H%M%SZ")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{str_start}",
                f"DTEND:{str_end}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(
        f"\n[+] Successfully generated '{filename}' with {len(seen_uids)} episode events."
    )


def main():
    if (
        SIMKL_CLIENT_ID == "YOUR_SIMKL_CLIENT_ID"
        or SIMKL_ACCESS_TOKEN == "YOUR_SIMKL_ACCESS_TOKEN"
    ):
        print(
            "[!] Please set your SIMKL_CLIENT_ID and SIMKL_ACCESS_TOKEN at the top of the script."
        )
        return

    watchlist_ids, direct_events = get_user_watchlist()
    calendar_events = get_global_calendar_events(watchlist_ids)

    # Combine events from both sources
    all_events = direct_events + calendar_events
    generate_ics(all_events, OUTPUT_FILENAME)


if __name__ == "__main__":
    main()
