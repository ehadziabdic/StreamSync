import os
import requests
from datetime import datetime

CLIENT_ID = os.environ.get("SIMKL_CLIENT_ID")
ACCESS_TOKEN = os.environ.get("SIMKL_ACCESS_TOKEN")
GIST_ID = os.environ.get("GIST_ID")
# Fallback to check both GH_PAT_TOKEN and GIST_TOKEN
GH_TOKEN = os.environ.get("GH_PAT_TOKEN") or os.environ.get("GIST_TOKEN")

def format_ics_dt(dt_str):
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        return None

def main():
    if not GH_TOKEN:
        print("❌ ERROR: GH_PAT_TOKEN environment variable is missing!")
        exit(1)

    simkl_headers = {
        "Content-Type": "application/json",
        "simkl-api-key": CLIENT_ID,
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    print("Fetching watchlist from Simkl...")
    # Fetch all shows with next_watch_info attached
    sync_res = requests.get(
        "https://api.simkl.com/sync/all-items/shows?next_watch_info=yes", 
        headers=simkl_headers
    )
    
    if sync_res.status_code != 200:
        print(f"❌ Error fetching watchlist from Simkl: {sync_res.status_code} - {sync_res.text}")
        exit(1)

    shows_data = sync_res.json()
    shows_list = shows_data.get("shows", [])
    print(f"Found {len(shows_list)} shows in your Simkl library.")

    watchlist_ids = set()
    events = []

    # 1. Collect integer Simkl IDs and parse immediate next episodes
    for item in shows_list:
        show = item.get("show", {})
        raw_id = show.get("ids", {}).get("simkl")
        if raw_id is not None:
            try:
                watchlist_ids.add(int(raw_id))
            except ValueError:
                pass

        next_info = item.get("next_to_watch_info")
        if next_info and next_info.get("date"):
            show_title = show.get("title", "Unknown Show")
            season = next_info.get("season", 0)
            episode = next_info.get("episode", 0)
            ep_code = f"S{season:02d}E{episode:02d}"
            ep_title = next_info.get("title") or ep_code
            
            summary = f"{show_title} - {ep_code} - {ep_title}"
            dt_formatted = format_ics_dt(next_info["date"])
            if dt_formatted:
                events.append((dt_formatted, summary, f"Simkl ID: {raw_id}"))

    # 2. Cross-reference with Simkl's global 33-day TV schedule
    print("Cross-referencing with Simkl 33-day TV schedule...")
    cal_res = requests.get("https://data.simkl.in/calendar/tv.json")
    if cal_res.status_code == 200:
        for item in cal_res.json():
            raw_id = item.get("ids", {}).get("simkl")
            if raw_id is not None and int(raw_id) in watchlist_ids:
                show_title = item.get("title", "Show")
                date_str = item.get("date")
                season = item.get("season", 0)
                episode = item.get("episode", 0)
                ep_title = item.get("episode_title") or f"S{season:02d}E{episode:02d}"
                
                summary = f"{show_title} - S{season:02d}E{episode:02d} - {ep_title}"
                dt_formatted = format_ics_dt(date_str)
                if dt_formatted:
                    events.append((dt_formatted, summary, f"Simkl ID: {raw_id}"))

    # 3. Also check Anime schedule in case you track anime shows
    anime_cal_res = requests.get("https://data.simkl.in/calendar/anime.json")
    if anime_cal_res.status_code == 200:
        for item in anime_cal_res.json():
            raw_id = item.get("ids", {}).get("simkl")
            if raw_id is not None and int(raw_id) in watchlist_ids:
                show_title = item.get("title", "Anime")
                date_str = item.get("date")
                episode = item.get("episode", 0)
                ep_title = item.get("episode_title") or f"E{episode:02d}"
                
                summary = f"{show_title} - E{episode:02d} - {ep_title}"
                dt_formatted = format_ics_dt(date_str)
                if dt_formatted:
                    events.append((dt_formatted, summary, f"Simkl ID: {raw_id}"))

    # Deduplicate events
    unique_events = {}
    for dt_str, summary, desc in events:
        unique_events[(dt_str, summary)] = desc

    print(f"Total calendar events found: {len(unique_events)}")

    # Build standard iCalendar format
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Simkl Calendar Exporter//EN",
        "X-WR-CALNAME:Simkl TV Calendar",
        "X-WR-TIMEZONE:UTC"
    ]

    for (dt_str, summary), desc in unique_events.items():
        ics_lines.extend([
            "BEGIN:VEVENT",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            f"DTSTART:{dt_str}",
            f"DTEND:{dt_str}",
            "END:VEVENT"
        ])

    ics_lines.append("END:VCALENDAR")
    ics_content = "\n".join(ics_lines)

    # Push to GitHub Gist using correct Bearer token authentication
    print("Updating GitHub Gist...")
    gist_headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "description": "Updated Simkl Calendar Feed",
        "files": {
            "trakt.ics": {
                "content": ics_content
            }
        }
    }
    gist_res = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}", 
        headers=gist_headers, 
        json=payload
    )
    
    if gist_res.status_code == 200:
        print("✅ SUCCESS: trakt.ics updated in GitHub Gist!")
    else:
        print(f"❌ Failed to update Gist: {gist_res.status_code} - {gist_res.text}")
        exit(1)

if __name__ == "__main__":
    main()
