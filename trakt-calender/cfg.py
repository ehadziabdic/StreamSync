import configparser
import os
from utils import Data

def createOrGetConfiguration(cfgFilepath):
    config = configparser.RawConfigParser()
    sec = 'TraktCalendarExporter'
    
    if not os.path.exists(cfgFilepath):
        print(f"One time configuration. Can change it later in {cfgFilepath}")
        traktUser = input("Trakt Username: ").strip()
        traktApiKey = input("Trakt API Key (Client ID): ").strip()
        userTimezone = input("User Timezone (e.g., Europe/London): ").strip()
        exportFile = input("Export File Path (e.g., trakt.ics): ").strip()
        descFormatInput = input("Event Description Format (default empty): ").strip()
        eventDescFormat = descFormatInput if descFormatInput else ""
        
        config.add_section(sec)
        config.set(sec, "TraktUser", traktUser)
        config.set(sec, "TraktApiKey", traktApiKey)
        config.set(sec, "UserTimezone", userTimezone)
        # Note: Trakt v2 API uses UTC, so we keep this as a fallback
        config.set(sec, "ShowsTimezone", "UTC") 
        config.set(sec, "ExportFilePath", exportFile)
        config.set(sec, "EventDescriptionFormat", eventDescFormat)

        with open(cfgFilepath, 'w') as configfile:
            config.write(configfile)
    else:
        config.read(cfgFilepath)
    
    result = {}
    # Added a check to handle missing keys in old config files
    for k in ["TraktUser", "TraktApiKey", "UserTimezone", "ShowsTimezone", "ExportFilePath", "EventDescriptionFormat"]:
        try:
            result[k] = config.get(sec, k)
        except configparser.NoOptionError:
            result[k] = ""

    return Data(result)