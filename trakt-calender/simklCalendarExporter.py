import os
import requests
from datetime import datetime

CLIENT_ID = os.environ.get("SIMKL_CLIENT_ID")
ACCESS_TOKEN = os.environ.get("SIMKL_ACCESS_TOKEN")
GIST_TOKEN = os.environ.get("GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID")

def format_ics_dt(dt_str):
    if not dt_str:
        return None
    # Normalize ISO format string for iCal (YYYYMMDDTHHMMSSZ)
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        return None

def main():
    headers = {
        "Content-Type": "application/json",
        "simkl-api-key": CLIENT_ID,
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    print("Fetching watchlist from Simkl...")
    # Fetch all shows in user's library with next episode metadata attached
    sync_res = requests.get(
        "https://api.simkl.com/sync/all-items/shows?next_watch_info=yes", 
        headers=headers
    )
    
    if sync_res.status_code != 200:
        print(f"Error fetching watchlist from Simkl: {sync_res.status_code} - {sync_res.text}")
        return

    shows_data = sync_res.json()
    shows_list = shows_data.get("shows", [])
    print(f"Found {len(shows_list)} shows in your Simkl library.")

    watchlist_ids = set()
    events = []

    # 1. Parse 'next_to_watch_info' from watchlist items
    for item in shows_list:
        show = item.get("show", {})
        simkl_id = show.get("ids", {}).get("simkl")
        if simkl_id:
            watchlist_ids.add(simkl_id)

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
                events.append((dt_formatted, summary, f"Simkl ID: {simkl_id}"))

    # 2. Query 33-day broadcast calendar and filter by user's watchlist
    print("Cross-referencing with Simkl 33-day TV schedule...")
    cal_res = requests.get("https://data.simkl.in/calendar/tv.json")
    if cal_res.status_code == 200:
        cal_items = cal_res.json()
        for item in cal_items:
            simkl_id = item.get("ids", {}).get("simkl")
            if simkl_id in watchlist_ids:
                show_title = item.get("title", "Show")
                date_str = item.get("date")
                season = item.get("season", 0)
                episode = item.get("episode", 0)
                ep_title = item.get("episode_title") or f"S{season:02d}E{episode:02d}"
                
                summary = f"{show_title} - S{season:02d}E{episode:02d} - {ep_title}"
                dt_formatted = format_ics_dt(date_str)
                if dt_formatted:
                    events.append((dt_formatted, summary, f"Simkl ID: {simkl_id}"))

    print(f"Total calendar events found: {len(events)}")

    # Deduplicate events by (date, summary)
    unique_events = {}
    for dt_str, summary, desc in events:
        unique_events[(dt_str, summary)] = desc

    # Build standard iCalendar file content
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

    # Push updated .ics content to GitHub Gist
    print("Updating GitHub Gist...")
    gist_headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
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
        print("Successfully updated trakt.ics in GitHub Gist!")
    else:
        print(f"Failed to update Gist: {gist_res.status_code} - {gist_res.text}")

if __name__ == "__main__":
    main()
