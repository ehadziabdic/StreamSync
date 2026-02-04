import os
import json
import requests
from uuid import uuid4
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import utc
from icalendar import Calendar, Event

# --- 1. SETTINGS ---
CLIENT_ID = os.environ.get('TRAKT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('TRAKT_CLIENT_SECRET')
GIST_ID = os.environ.get('GIST_ID')
GH_TOKEN = os.environ.get('GH_PAT_TOKEN')
API_URL = "https://api.trakt.tv"

# --- 2. TOKEN PERSISTENCE LOGIC (GIST) ---
def get_stored_tokens():
    """Fetches tokens from the Gist. If not found, falls back to GitHub Secrets."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"Bearer {GH_TOKEN}"}
    resp = requests.get(url, headers=headers).json()
    
    if 'token.json' in resp.get('files', {}):
        return json.loads(resp['files']['token.json']['content'])
    
    # Fallback for the very first run
    return {"refresh_token": os.environ.get('TRAKT_REFRESH_TOKEN')}

def update_gist_files(ics_content, new_tokens):
    """Saves both the new calendar and the new refresh token to the Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "files": {
            "trakt.ics": {"content": ics_content},
            "token.json": {"content": json.dumps(new_tokens)}
        }
    }
    r = requests.patch(url, headers=headers, json=data)
    if r.status_code == 200:
        print("Successfully updated Gist with new Calendar and Token.")
    else:
        print(f"Failed to update Gist: {r.text}")

# --- 3. TRAKT API LOGIC ---
def get_access_token():
    tokens = get_stored_tokens()
    url = f"{API_URL}/oauth/token"
    data = {
        "refresh_token": tokens['refresh_token'],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "refresh_token"
    }
    response = requests.post(url, json=data)
    res_data = response.json()
    
    if 'access_token' not in res_data:
        raise Exception(f"Trakt Refresh Failed: {res_data}")
        
    return res_data['access_token'], res_data

def loadShows(access_token):
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/calendars/my/shows/{today}/60"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    events = []
    for entry in response.json():
        ep = entry['episode']
        sh = entry['show']
        airtime = datetime.strptime(entry['first_aired'][:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=utc)
        events.append({
            "summary": f"{sh['title']} S{str(ep['season']).zfill(2)}E{str(ep['number']).zfill(2)} \"{ep['title']}\"",
            "start": airtime,
            "end": airtime + relativedelta(minutes=sh.get('runtime', 30))
        })
    return events

# --- 4. RUN ---
def main():
    # 1. Get tokens & Refresh
    access_token, new_tokens = get_access_token()
    
    # 2. Build Calendar
    cal = Calendar()
    cal.add('x-wr-calname', 'My Trakt Schedule')
    for ev in loadShows(access_token):
        event = Event()
        event.add('summary', ev['summary'])
        event.add('dtstart', ev['start'])
        event.add('dtend', ev['end'])
        event.add('dtstamp', datetime.now(utc))
        event.add('uid', f"{uuid4()}@trakt")
        cal.add_component(event)
    
    # 3. Save everything to Gist in one go
    update_gist_files(cal.to_ical().decode('utf-8'), new_tokens)

if __name__ == "__main__":
    main()