import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta

SIMKL_CLIENT_ID = os.environ.get("SIMKL_CLIENT_ID")
SIMKL_ACCESS_TOKEN = os.environ.get("SIMKL_ACCESS_TOKEN")
GIST_ID = os.environ.get("GIST_ID")
GH_TOKEN = os.environ.get("GH_PAT_TOKEN") or os.environ.get("GIST_TOKEN")


def safe_int(val, default=1):
    if isinstance(val, dict):
        val = val.get("number") or val.get("season") or val.get("episode")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def fetch_json(url, headers=None):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "SimklCalendarExporter/4.4"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"    [!] HTTP {e.code} fetching {url}: {e.reason}")
        return None
    except Exception as e:
        print(f"    [!] Error fetching {url}: {type(e).__name__}: {e}")
        return None


def clean_string(text):
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


# normalize provider-key variants (tvdb / tvdb_id) to one canonical name
PROVIDER_ALIASES = {
    "simkl_id": "simkl", "tvdb_id": "tvdb", "imdb_id": "imdb",
    "tmdb_id": "tmdb", "mal_id": "mal",
}


def extract_all_ids(obj):
    """Returns provider-namespaced ids like 'tvdb:12345' so a tvdb id can
    never be confused with an unrelated mal/tmdb id that has the same number."""
    ids = set()
    if not isinstance(obj, dict):
        return ids
    targets = [obj, obj.get("show"), obj.get("anime"), obj.get("movie"), obj.get("ids")]
    for t in targets:
        if isinstance(t, dict):
            for k in ["simkl", "simkl_id", "tvdb", "tvdb_id", "imdb", "imdb_id", "tmdb", "tmdb_id", "mal", "mal_id"]:
                val = t.get(k)
                if val is not None and str(val).strip() not in ("", "0", "None", "null"):
                    provider = PROVIDER_ALIASES.get(k, k)
                    ids.add(f"{provider}:{val}")
            ids_dict = t.get("ids")
            if isinstance(ids_dict, dict):
                for provider, val in ids_dict.items():
                    if val is not None and str(val).strip() not in ("", "0", "None", "null"):
                        provider = PROVIDER_ALIASES.get(provider, provider)
                        ids.add(f"{provider}:{val}")
    return ids


CATEGORY_KEY = {"shows": "show", "anime": "anime", "movies": "movie"}
ALLOWED_STATUSES = {
    "shows": {"watching", "plantowatch", "plan_to_watch", "plan to watch", "hold", "completed"},
    "anime": {"watching", "plantowatch", "plan_to_watch", "plan to watch", "hold", "completed"},
    "movies": {"watching", "plantowatch", "plan_to_watch", "plan to watch", "hold"},
}


def get_user_watchlist():
    headers = {
        "Authorization": f"Bearer {SIMKL_ACCESS_TOKEN}",
        "simkl-api-key": SIMKL_CLIENT_ID,
    }

    user_ids = {"shows": set(), "anime": set(), "movies": set()}
    user_titles = {"shows": set(), "anime": set(), "movies": set()}
    direct_events = []
    watchlist_movies = []  # [{"simkl_id": ..., "title": ...}, ...]

    for category in ["shows", "anime", "movies"]:
        url = f"https://api.simkl.com/sync/all-items/{category}?next_watch_info=yes"
        print(f"[*] Fetching watchlist for: {category}...")
        data = fetch_json(url, headers=dict(headers))
        if not data:
            print(f"    [!] No data returned for {category} watchlist.")
            continue

        items = data.get(category, []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        active_count = 0
        for item in items:
            status = str(item.get("status", "")).lower()
            if status not in ALLOWED_STATUSES[category]:
                continue

            active_count += 1
            nested_key = CATEGORY_KEY[category]
            show_obj = item.get(nested_key) or item.get("show") or item.get("anime") or item.get("movie") or item

            item_ids = extract_all_ids(show_obj)
            user_ids[category].update(item_ids)
            raw_title = show_obj.get("title", "")
            cleaned = clean_string(raw_title)
            if cleaned:
                user_titles[category].add(cleaned)

            if category == "movies":
                simkl_id = None
                ids_dict = show_obj.get("ids") if isinstance(show_obj.get("ids"), dict) else {}
                simkl_id = ids_dict.get("simkl") or ids_dict.get("simkl_id")
                if simkl_id:
                    watchlist_movies.append({"simkl_id": str(simkl_id), "title": raw_title or "Movie"})
                else:
                    print(f"    [!] No simkl id found for movie '{raw_title}', can't look up release date.")

            next_info = item.get("next_to_watch_info")
            if next_info and isinstance(next_info, dict):
                ep_date = next_info.get("date") or next_info.get("release_date")
                if ep_date:
                    direct_events.append(
                        {
                            "title": raw_title or "Title",
                            "season": safe_int(next_info.get("season"), 1) if category != "movies" else None,
                            "episode": safe_int(next_info.get("episode"), 1) if category != "movies" else None,
                            "ep_title": next_info.get("title", ""),
                            "date": ep_date,
                            "type": category,
                            # NOTE: carry the watchlist item's own ids through, so this
                            # event can be recognized as a duplicate of a calendar-feed
                            # match for the same underlying show.
                            "ids": item_ids,
                        }
                    )

        print(f"    Found {active_count} active items in {category}.")

    return user_ids, user_titles, direct_events, watchlist_movies


def get_calendar_events(user_ids, user_titles):
    """Shows + anime only now - these feeds are confirmed working."""
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month
    next_month_dt = (now.replace(day=28) + timedelta(days=4)).replace(day=1)

    calendar_urls = [
        ("https://data.simkl.in/calendar/tv.json", "shows"),
        ("https://data.simkl.in/calendar/anime.json", "anime"),
        (f"https://data.simkl.in/calendar/{current_year}/{current_month}/tv.json", "shows"),
        (f"https://data.simkl.in/calendar/{current_year}/{current_month}/anime.json", "anime"),
        (f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/tv.json", "shows"),
        (f"https://data.simkl.in/calendar/{next_month_dt.year}/{next_month_dt.month}/anime.json", "anime"),
    ]

    matched_events = []

    for url, category in calendar_urls:
        print(f"[*] Scanning feed: {url}...")
        feed = fetch_json(url)
        if not feed or not isinstance(feed, list):
            print("    [!] Feed returned nothing usable.")
            continue

        nested_key = CATEGORY_KEY[category]
        cat_ids = user_ids[category]
        cat_titles = user_titles[category]

        feed_matches = 0
        for entry in feed:
            entry_ids = extract_all_ids(entry)
            nested_obj = entry.get(nested_key)
            if not isinstance(nested_obj, dict):
                nested_obj = entry.get("show") if isinstance(entry.get("show"), dict) else {}

            entry_title = (
                entry.get(f"{nested_key}_title")
                or entry.get("show_title")
                or entry.get("anime_title")
                or nested_obj.get("title")
                or entry.get("title", "")
            )
            cleaned_entry_title = clean_string(entry_title)

            id_match = bool(entry_ids & cat_ids)
            title_match = cleaned_entry_title in cat_titles if cleaned_entry_title else False

            if id_match or title_match:
                feed_matches += 1
                matched_events.append(
                    {
                        "title": entry_title or "Title",
                        "season": safe_int(entry.get("season") or nested_obj.get("season"), 1),
                        "episode": safe_int(entry.get("episode") or nested_obj.get("episode"), 1),
                        "ep_title": entry.get("episode_title") or entry.get("title", ""),
                        "date": entry.get("date") or entry.get("air_date") or entry.get("release_date"),
                        "type": category,
                        # Full id set for this feed entry (simkl/tvdb/mal/imdb/tmdb).
                        # This is what lets us recognize the SAME show being matched
                        # via two different feeds/categories under two different
                        # display titles (e.g. tv.json's English title vs anime.json's
                        # romaji title for the same series).
                        "ids": entry_ids,
                    }
                )

        print(f"    Matched {feed_matches} entries.")

    return matched_events


# Candidate field names for a movie's release date, tried in order.
RELEASE_DATE_FIELDS = [
    "release_date",
    "theater_release_date",
    "theater_date",
    "us_release_date",
    "digital_release_date",
]


def extract_from_release_dates(release_dates, released_fallback):
    """release_dates is usually a list of per-country/type release entries,
    e.g. [{"country": "us", "type": "theatrical", "date": "2026-12-18T00:00:00Z"}, ...]
    Prefer a US entry, else the earliest date found. Falls back to `released`."""
    candidates = []

    if isinstance(release_dates, list):
        for entry in release_dates:
            if not isinstance(entry, dict):
                continue
            d = entry.get("date") or entry.get("release_date")
            if d:
                candidates.append((entry.get("country", ""), entry.get("type", ""), d))
    elif isinstance(release_dates, dict):
        for country, val in release_dates.items():
            if isinstance(val, str):
                candidates.append((country, "", val))
            elif isinstance(val, dict) and val.get("date"):
                candidates.append((country, val.get("type", ""), val["date"]))
            elif isinstance(val, list):
                for entry in val:
                    if isinstance(entry, dict) and entry.get("date"):
                        candidates.append((country, entry.get("type", ""), entry["date"]))

    if not candidates:
        return released_fallback, "released (fallback)"

    us_candidates = [c for c in candidates if str(c[0]).lower() in ("us", "usa", "united states")]
    pool = us_candidates or candidates
    pool.sort(key=lambda c: parse_iso_date(c[2]) or datetime.max)
    return pool[0][2], f"release_dates[{pool[0][0]}/{pool[0][1]}]"


def get_movie_events(watchlist_movies):
    """Look up each plan-to-watch movie individually - no broken bulk feed needed."""
    headers = {
        "Authorization": f"Bearer {SIMKL_ACCESS_TOKEN}",
        "simkl-api-key": SIMKL_CLIENT_ID,
    }
    events = []

    for movie in watchlist_movies:
        url = f"https://api.simkl.com/movies/{movie['simkl_id']}?extended=full"
        print(f"[*] Looking up movie: {movie['title']} ({movie['simkl_id']})...")
        data = fetch_json(url, headers=dict(headers))
        if not isinstance(data, dict):
            print("    [!] No data returned.")
            continue

        date_val = None
        used_field = None
        for field in RELEASE_DATE_FIELDS:
            if data.get(field):
                date_val = data[field]
                used_field = field
                break

        if not date_val:
            date_val, used_field = extract_from_release_dates(
                data.get("release_dates"), data.get("released")
            )

        if not date_val:
            print(f"    [!] Still no usable date. Raw release_dates: {data.get('release_dates')!r}, "
                  f"released: {data.get('released')!r}")
            continue

        print(f"    [debug] using field '{used_field}' = {date_val}")

        # Pull ids from the full movie payload too, plus the simkl id we already know.
        movie_ids = extract_all_ids(data)
        movie_ids.add(f"simkl:{movie['simkl_id']}")

        events.append(
            {
                "title": movie["title"],
                "season": None,
                "episode": None,
                "ep_title": "",
                "date": date_val,
                "type": "movies",
                "ids": movie_ids,
            }
        )

    return events


def parse_iso_date(date_str):
    if not date_str:
        return None
    clean_str = str(date_str).replace("Z", "").replace("T", " ").split("+")[0].split(".")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    return None


def merge_duplicate_events(events):
    """Collapse events that refer to the same underlying episode/movie even when
    they were sourced from different feeds/categories under different display
    titles (e.g. an anime matched via both the general tv.json feed and the
    anime.json feed, or a show tracked as both 'show' and 'anime' in Simkl).

    Two events are considered the same if they share a season+episode (or are
    both movies) AND either share at least one provider id, or have an
    identical normalized title. Union-find groups all matches transitively,
    then we keep one representative per group (preferring the one that has a
    resolvable date and, as a tiebreaker, an actual episode title)."""
    n = len(events)
    if n == 0:
        return events

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def bucket_key_of(ev):
        is_movie = ev.get("type") == "movies" or (ev.get("season") is None and ev.get("episode") is None)
        if is_movie:
            return ("movie",)
        return ("tv", safe_int(ev.get("season"), 1), safe_int(ev.get("episode"), 1))

    buckets = {}
    for i, ev in enumerate(events):
        buckets.setdefault(bucket_key_of(ev), []).append(i)

    for idxs in buckets.values():
        for a_pos in range(len(idxs)):
            for b_pos in range(a_pos + 1, len(idxs)):
                i, j = idxs[a_pos], idxs[b_pos]
                ids_i = events[i].get("ids") or set()
                ids_j = events[j].get("ids") or set()
                same_title = clean_string(events[i]["title"]) == clean_string(events[j]["title"])
                shares_id = bool(ids_i and ids_j and (ids_i & ids_j))
                if shares_id or same_title:
                    union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for idxs in groups.values():
        best = None
        for i in idxs:
            ev = events[i]
            if not parse_iso_date(ev.get("date")):
                continue
            if best is None:
                best = ev
            elif not best.get("ep_title") and ev.get("ep_title"):
                best = ev
        if best is None:
            best = events[idxs[0]]
        merged.append(best)

    return merged


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

    seen_keys = set()
    now_cutoff = datetime.utcnow() - timedelta(days=1)

    for ev in events:
        dt_start = parse_iso_date(ev.get("date"))
        if not dt_start:
            continue
        if dt_start < now_cutoff:
            continue

        dt_end = dt_start + timedelta(minutes=45)
        is_movie = ev.get("type") == "movies" or (ev.get("season") is None and ev.get("episode") is None)
        title_safe = clean_string(ev["title"])

        # Prefer a stable provider id for the dedup/UID key (simkl's own id is
        # universal across a show's "shows" and "anime" list entries, so it's
        # the most reliable). Fall back to title text only if no id is present.
        ids = ev.get("ids") or set()
        canonical_id = next((i for i in ids if i.startswith("simkl:")), None) or (sorted(ids)[0] if ids else None)
        key_id = canonical_id or title_safe

        if is_movie:
            summary = f"{ev['title']}"
            dedup_key = f"movie-{key_id}"
        else:
            season = safe_int(ev.get("season"), 1)
            episode = safe_int(ev.get("episode"), 1)
            ep_code = f"S{season:02d}E{episode:02d}"
            summary = f"{ev['title']} {ep_code}"
            dedup_key = f"tv-{key_id}-s{season:02d}e{episode:02d}"

        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        description = ev["ep_title"] if ev.get("ep_title") else f"Release: {ev['title']}"
        uid_str = re.sub(r"[^a-zA-Z0-9:_-]", "", dedup_key)

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
    return "\n".join(lines), len(seen_keys)


def update_gist(ics_content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SimklCalendarExporter/4.4",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = json.dumps(
        {"description": "Updated Simkl TV Calendar", "files": {"trakt.ics": {"content": ics_content}}}
    ).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
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
        var for var, val in [
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

    user_ids, user_titles, direct_events, watchlist_movies = get_user_watchlist()
    calendar_events = get_calendar_events(user_ids, user_titles)
    movie_events = get_movie_events(watchlist_movies)

    all_events = direct_events + calendar_events + movie_events
    print(f"\n[*] {len(all_events)} raw event candidates before merge.")

    merged_events = merge_duplicate_events(all_events)
    print(f"[*] {len(merged_events)} after merging cross-feed duplicates.")

    ics_content, event_count = generate_ics(merged_events)

    print(f"\n[+] Generated calendar with {event_count} active upcoming events.")
    update_gist(ics_content)


if __name__ == "__main__":
    main()
