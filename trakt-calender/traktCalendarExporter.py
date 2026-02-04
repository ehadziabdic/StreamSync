import os, json, requests
from pytz import timezone, utc
from uuid import uuid4
from icalendar import Calendar, Event
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cfg import createOrGetConfiguration
from utils import Data, padWithZero

API_URL = "https://api.trakt.tv"
TOKEN_FILE = os.path.expanduser('~/.trakt_token.json')

cfgFile = os.path.expanduser('~/.traktCalExporter.cfg')
cfg = createOrGetConfiguration(cfgFile)

# --- CLASS DEFINITION (This was missing!) ---
class EpisodeEvent(object):
    def __init__(self, show, title, season, number, runtime, airtime):
        self.show, self.title, self.season, self.number, self.runtime, self.airtime = show, title, season, number, runtime, airtime
        self.summary = f'{show} S{season}E{number} "{title}"'

    def formatDescription(self, fmt):
        try:
            return fmt % self.__dict__
        except:
            return self.summary

# --- AUTHENTICATION LOGIC ---
def get_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)['access_token']
    
    print("--- TRAKT LOGIN REQUIRED ---")
    auth_url = f"https://trakt.tv/oauth/authorize?response_type=code&client_id={cfg.TraktApiKey}&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
    print(f"1. Go to: {auth_url}")
    pin = input("2. Paste the PIN from that page here: ").strip()
    
    # You will need to enter your secret once more
    secret = input("3. Enter your Client Secret (from Trakt website): ").strip()
    
    data = {
        "code": pin,
        "client_id": cfg.TraktApiKey,
        "client_secret": secret,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "authorization_code"
    }
    
    response = requests.post(f"{API_URL}/oauth/token", json=data)
    token_data = response.json()
    
    if 'access_token' not in token_data:
        print("Login failed. Check your Secret and PIN.")
        exit()

    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    
    return token_data['access_token']

# --- CALENDAR FETCHING ---
def loadShows():
    token = get_access_token()
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": cfg.TraktApiKey,
        "Authorization": f"Bearer {token}"
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/calendars/my/shows/{today}/90"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    for entry in response.json():
        episode_data = entry['episode']
        show_data = entry['show']
        air_at_str = entry['first_aired']
        
        # Parse UTC time
        airtime = datetime.strptime(air_at_str[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=utc)
        
        yield EpisodeEvent(
            show_data['title'], 
            episode_data['title'], 
            padWithZero(episode_data['season'], 2), 
            padWithZero(episode_data['number'], 2), 
            show_data.get('runtime', 30), 
            airtime
        )

# --- FILE HANDLING ---
def openOrCreateCalendar():
    if os.path.exists(cfg.ExportFilePath):
        try:
            with open(cfg.ExportFilePath, 'rb') as opened:
                return Calendar.from_ical(opened.read())
        except:
            pass

    cal = Calendar()
    cal.add('prodid', '-//Trakt Personal Calendar//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'My Trakt Schedule')
    return cal

def createCalendar():
    cal = openOrCreateCalendar()
    existing_summaries = [e.get('summary') for e in cal.walk('vevent')]

    count = 0
    for episodeEvent in loadShows():
        if episodeEvent.summary in existing_summaries:
            continue

        event = Event()
        event.add('summary', episodeEvent.summary)
        event.add('dtstart', episodeEvent.airtime)
        event.add('dtend', episodeEvent.airtime + relativedelta(minutes=episodeEvent.runtime))
        event.add('dtstamp', datetime.now(utc))
        event.add('uid', f"{uuid4()}@trakt")
        event.add('description', episodeEvent.formatDescription(cfg.EventDescriptionFormat))

        cal.add_component(event)
        count += 1
    
    with open(cfg.ExportFilePath, 'wb') as f:
        f.write(cal.to_ical())
    
    print(f"Done! Added {count} new episodes to {cfg.ExportFilePath}")

if __name__ == "__main__":
    createCalendar()