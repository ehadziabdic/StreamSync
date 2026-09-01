<div align="center">

🎬

# Simkl Calendar Sync

**Automatic synchronization of your Simkl watchlist (TV shows, anime, and movies) into an iCalendar (.ics) file hosted on a GitHub Gist — ready to be consumed by Stremio, Google Calendar, or any iCal-compatible app.**

Automation • Python • Simkl API • GitHub Actions

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Simkl](https://img.shields.io/badge/Simkl-API-orange)
![GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=github-actions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [How It Works](#-how-it-works)
- [Technologies](#️-technologies)
- [Project Structure](#-project-structure)
- [Setup & Deployment](#-setup--deployment)
- [Usage](#-usage)
- [Contact](#-contact)

---

## 🎯 Overview

This project keeps your entertainment calendar up to date **automatically**. It pulls your personal Simkl watchlist — including TV shows, anime, and movies — cross-references it with Simkl's public calendar feeds for upcoming episodes and releases, and generates a clean `.ics` calendar file that gets pushed to a GitHub Gist every week.

The generated calendar can be imported into **Stremio** (via the iCal addon), **Google Calendar**, **Apple Calendar**, or any other app that supports the iCalendar format.

### What It Does

1. **Fetches** your Simkl watchlist (shows, anime, movies) with current status
2. **Scans** Simkl's CDN calendar feeds for upcoming episodes and premiere dates
3. **Matches** watchlist items against calendar entries using multi-provider ID resolution (Simkl, TMDB, TVDB, IMDB, MAL)
4. **Generates** a clean `.ics` file with properly formatted events including season/episode info
5. **Uploads** the calendar to a GitHub Gist for public consumption
6. **Runs** automatically every Monday via GitHub Actions — or on demand

---

## ✨ Features

### Data Pipeline

- 🔄 **Automatic Weekly Sync** — GitHub Actions runs every Monday at midnight
- 🎬 **Multi-Category Tracking** — TV shows, anime, and movies in one calendar
- 📡 **Dual Data Sources** — Simkl watchlist API + CDN calendar feeds for maximum coverage
- 🆔 **Multi-Provider ID Resolution** — Simkl, TMDB, TVDB, IMDB, MAL ID matching eliminates duplicates across feeds

### Calendar Generation

- 📅 **Clean ICS Output** — Standard iCalendar format compatible with Stremio, Google Calendar, Apple Calendar
- 🏷️ **Season & Episode Labels** — Events include S01E05-style descriptions
- 🎥 **Movie Release Dates** — Upcoming movie premieres included from watchlist data
- 🔀 **Smart Deduplication** — Duplicate events from multiple feeds are merged intelligently
- 📊 **Watchlist Diagnostics** — Detailed logging shows which items matched and why

### Reliability

- ⏱️ **Robust Fetching** — Configurable timeouts with graceful HTTP error handling
- 🧪 **Zero External Dependencies** — Uses only Python stdlib (json, urllib, datetime)
- 📝 **Structured Logging** — Clear console output for debugging sync issues

---

## 🛠️ Technologies

### Core

- **Python 3.12** — Scripting language (stdlib only, no pip packages needed)
- **Simkl API** — Watchlist data via `api.simkl.com/sync/all-items/`
- **Simkl CDN** — Calendar feeds via `data.simkl.in/calendar/`

### Infrastructure

- **GitHub Actions** — Automated weekly execution (Monday 00:00 UTC)
- **GitHub Gist** — Hosts the generated `.ics` file as a public endpoint
- **iCalendar (ICS)** — Standard format for calendar interoperability

### APIs & Data

| Source | Purpose |
| :--- | :--- |
| `api.simkl.com` | User watchlist with status, next-episode info |
| `data.simkl.in/calendar/tv.json` | Global TV show episode schedule |
| `data.simkl.in/calendar/anime.json` | Global anime episode schedule |
| `data.simkl.in/calendar/{YYYY}/{MM}/tv.json` | Monthly TV archives |
| `data.simkl.in/calendar/{YYYY}/{MM}/anime.json` | Monthly anime archives |

---

## 🏗️ Architecture

### Data Flow

```txt
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Simkl API  │────▶│  Python      │────▶│  GitHub Gist │
│  (watchlist │     │  Exporter    │     │  (simkl.ics) │
│   + CDN)    │     │  (stdlib)    │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
                           │                    │
                    GitHub Actions         Stremio / Google
                    (weekly cron)          Calendar / etc.
```

### Processing Pipeline

1. **Watchlist Fetch** — Pulls all items per category with status filtering
2. **ID Extraction** — Normalizes provider IDs across all nested objects
3. **Calendar Scan** — Iterates monthly CDN feeds for episode air dates
4. **Event Matching** — Cross-references watchlist IDs against calendar entries
5. **Movie Lookup** — Queries individual movie release dates via Simkl API
6. **Deduplication** — Merges overlapping events from direct + CDN sources
7. **ICS Generation** — Produces RFC 5545-compliant calendar output
8. **Gist Upload** — Pushes final `.ics` to GitHub Gist via REST API

---

## 📁 Project Structure

```txt
StremioServer/
├── sync/
│   ├── simklCalendarExporter.py    # ✅ Main script — fetches, processes, generates ICS
│   └── .github/workflows/
│       └── calender_sync.yml       # GitHub Actions workflow (weekly + manual)
├── trakt-calender/
│   ├── traktCalendarExporter.py    # Older/alternate calendar exporter
│   └── trakt.ics                   # Legacy ICS output
├── stremio-host/
│   ├── docker-compose.yml          # Dockerized Stremio server
│   └── update-gist.ps1            # Gist update utility
├── get_token.py                    # Simkl OAuth token retrieval helper
├── index.html                      # Web interface
└── README.md                       # This file
```

---

## 🚀 Setup & Deployment

### Prerequisites

- Python 3.12 or higher
- A Simkl account with API access
- A GitHub account (for Gist hosting)
- GitHub Actions enabled on the repository

### Environment Variables

| Variable | Description |
| :--- | :--- |
| `SIMKL_CLIENT_ID` | Your Simkl API client ID |
| `SIMKL_ACCESS_TOKEN` | Your Simkl OAuth access token |
| `GIST_ID` | ID of the GitHub Gist to upload the `.ics` file to |
| `GH_PAT_TOKEN` | GitHub Personal Access Token with gist scope |

### Running Locally

```bash
# Clone the repository
git clone https://github.com/ehadziabdic/StreamSync.git
cd StreamSync

# Set environment variables
export SIMKL_CLIENT_ID="your_client_id"
export SIMKL_ACCESS_TOKEN="your_access_token"
export GIST_ID="your_gist_id"
export GH_PAT_TOKEN="your_github_pat"

# Run the exporter
python sync/simklCalendarExporter.py
```

### GitHub Actions Setup

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Add the four required secrets listed above
3. The workflow runs automatically every Monday at 00:00 UTC
4. To trigger manually: **Actions** → **Calendar Sync** → **Run workflow**

---

## 📖 Usage

### As a Stremio Calendar

Once the `.ics` is hosted on your Gist, add it to Stremio via the **iCal Feed** addon or any calendar-compatible addon.

### As a Google Calendar

1. Get the raw Gist URL: `https://gist.githubusercontent.com/<user>/<gist_id>/raw/simkl.ics`
2. Go to Google Calendar → Settings → Import & Export → Import
3. Paste the URL or upload the `.ics` file

### Direct ICS Download

The latest calendar is always available at:

```
https://gist.githubusercontent.com/<user>/<gist_id>/raw/simkl.ics
```

---

## 📧 Contact

**Emin Hadžiabdić**
Data Science and AI Student
ETF Sarajevo

- GitHub: [@ehadziabdic](https://github.com/ehadziabdic)

---

⭐ Star this repo if you found it useful!