import os
import requests
from uuid import uuid4
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import utc
from icalendar import Calendar, Event

CLIENT_ID = os.environ.get('SIMKL_CLIENT_ID')
ACCESS_TOKEN = os.environ.get('SIMKL_ACCESS_TOKEN')
GIST_ID = os.environ.get('GIST_ID')
GH_TOKEN = os.environ.get('GH_PAT_TOKEN')

def parse_dt(val):
    if not val:
        return None
    try:
        if "T" in val:
            return datetime.strptime(val[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=utc)
        return datetime.strptime(val[:10], '%Y-%m-%d').replace(tzinfo=utc)
    except Exception:
        return None

def fetch_upcoming_episodes():
    url = "https://api.simkl.com/tv/episodes/to-watch"
    headers = {
        "Content-Type": "application/json",
        "simkl-api-key": CLIENT_ID,
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"Failed to fetch: {res.status_code}")
        return []

    events = []
    for item in res.json():
        show = item.get('show', {})
        ep = item.get('episode', {})
        airtime = parse_dt(ep.get('date') or ep.get('first_aired'))
        if not airtime:
            continue

        runtime = int(show.get('runtime') or 30)
        s = str(ep.get('season', 1)).zfill(2)
        e = str(ep.get('episode', 1)).zfill(2)
        title = ep.get('title', '')
        summary = f"{show.get('title', 'Show')} S{s}E{e}" + (f' "{title}"' if title else "")

        events.append({
            "summary": summary,
            "start": airtime,
            "end": airtime + relativedelta(minutes=runtime)
        })
    return events

def update_gist(ics_text):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "description": "Simkl Calendar Feed",
        "files": {
            "trakt.ics": {"content": ics_text}  # Kept as trakt.ics so your calendar link stays the same
        }
    }
    r = requests.patch(url, headers=headers, json=payload)
    if r.status_code == 200:
        print("✅ Calendar successfully updated in Gist!")
    else:
        print(f"❌ Failed to update Gist: {r.status_code} {r.text}")
        exit(1)

def main():
    cal = Calendar()
    cal.add('x-wr-calname', 'Simkl Calendar')
    
    for ev in fetch_upcoming_episodes():
        event = Event()
        event.add('summary', ev['summary'])
        event.add('dtstart', ev['start'])
        event.add('dtend', ev['end'])
        event.add('dtstamp', datetime.now(utc))
        event.add('uid', f"{uuid4()}@simkl")
        cal.add_component(event)

    update_gist(cal.to_ical().decode('utf-8'))

if __name__ == "__main__":
    main()
