import os
import json
import requests
from uuid import uuid4
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import utc
from icalendar import Calendar, Event

# --- 1. SETTINGS FROM GITHUB SECRETS ---
# These must match the names you saved in Settings > Secrets > Actions
CLIENT_ID = os.environ.get('TRAKT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('TRAKT_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('TRAKT_REFRESH_TOKEN')

API_URL = "https://api.trakt.tv"
OUTPUT_FILE = "trakt.ics"

# --- 2. DATA HELPER ---
class EpisodeEvent(object):
    def __init__(self, show, title, season, number, runtime, airtime):
        self.show = show
        self.title = title
        self.season = str(season).zfill(2)
        self.number = str(number).zfill(2)
        self.runtime = runtime
        self.airtime = airtime
        self.summary = f'{self.show} S{self.season}E{self.number} "{self.title}"'

# --- 3. TRAKT API LOGIC ---
def get_access_token():
    """Uses the Refresh Token to get a fresh Access Token for this run."""
    url = f"{API_URL}/oauth/token"
    data = {
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "refresh_token"
    }
    response = requests.post(url, json=data)
    response_data = response.json()
    
    if 'access_token' not in response_data:
        raise Exception(f"Failed to refresh token: {response_data}")
        
    return response_data['access_token']

def loadShows():
    """Fetches your personal 60-day calendar from Trakt."""
    token = get_access_token()
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    # Fetching 60 days of YOUR shows
    url = f"{API_URL}/calendars/my/shows/{today}/60"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Trakt API Error: {response.status_code}")
        return

    for entry in response.json():
        ep = entry['episode']
        sh = entry['show']
        # Parse ISO timestamp to UTC
        airtime = datetime.strptime(entry['first_aired'][:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=utc)
        
        yield EpisodeEvent(
            sh['title'], 
            ep['title'], 
            ep['season'], 
            ep['number'], 
            sh.get('runtime', 30), 
            airtime
        )

# --- 4. CALENDAR GENERATION ---
def createCalendar():
    cal = Calendar()
    cal.add('prodid', '-//Trakt Personal Calendar//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'My Trakt Schedule')

    count = 0
    for ev in loadShows():
        event = Event()
        event.add('summary', ev.summary)
        event.add('dtstart', ev.airtime)
        event.add('dtend', ev.airtime + relativedelta(minutes=ev.runtime))
        event.add('dtstamp', datetime.now(utc))
        event.add('uid', f"{uuid4()}@trakt")
        
        cal.add_component(event)
        count += 1
    
    with open(OUTPUT_FILE, 'wb') as f:
        f.write(cal.to_ical())
    
    print(f"Successfully generated {OUTPUT_FILE} with {count} episodes.")

if __name__ == "__main__":
    createCalendar()