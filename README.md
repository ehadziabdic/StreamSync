<div align="center">

🎬

# StreamSync

**Self-hosted Stremio server with remote access + automatic Simkl watchlist-to-calendar synchronization.**

Automation • Python • Docker • GitHub Actions

![Python](https://img.shields.io/badge/Python-3.12-yellow?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-green?logo=github-actions&logoColor=white)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Server](#-server)
- [Calendar Sync](#-calendar-sync)
- [Setup](#-setup)
- [Contact](#-contact)

---

## 🎯 Overview

This project has two parts that work together:

1. **Server** — A Dockerized Stremio server exposed to the internet via Cloudflare Tunnel, so you can connect from any device (phone, tablet, laptop) using a simple redirect page hosted on GitHub Pages.

2. **Calendar Sync** — A Python script that pulls your Simkl watchlist (TV shows, anime, movies), matches upcoming episodes and releases, and pushes an `.ics` calendar to a GitHub Gist every week via GitHub Actions.

---

## 🖥️ Server

Runs Stremio Server in Docker and exposes it through a Cloudflare quick tunnel. A lightweight web page reads the current tunnel URL from a Gist and redirects you automatically.

```txt
Phone/Laptop → index.html (GitHub Pages) → Gist (tunnel URL) → Cloudflare Tunnel → Stremio Server (Docker)
```

### Components

- `docker-compose.yml` — Stremio Server + Cloudflare tunnel containers
- `update-gist.ps1` — Extracts the tunnel URL from Docker logs and publishes it to a GitHub Gist
- `web/index.html` — Simple redirect page that fetches the URL from the Gist and forwards you to the server

---

## 📅 Calendar Sync

Fetches your Simkl watchlist and generates an `.ics` calendar with upcoming episodes and movie releases. Runs weekly via GitHub Actions and uploads the result to a GitHub Gist.

### What It Does

1. Pulls your watchlist (shows, anime, movies) from the Simkl API
2. Scans Simkl's CDN calendar feeds for upcoming episodes
3. Matches items using multi-provider IDs (Simkl, TMDB, TVDB, IMDB, MAL)
4. Generates a clean `.ics` file with season/episode labels
5. Uploads to a GitHub Gist — importable into Stremio, Google Calendar, Apple Calendar, etc.

### Files

- `sync/simklCalendarExporter.py` — Main script (stdlib only, no dependencies)
- `.github/workflows/calender_sync.yml` — Runs every Monday + manual dispatch

---

## 🚀 Setup

### Server

```bash
cd server/docker
docker compose up -d
```

Then run `update-gist.ps1` to publish the tunnel URL to your Gist. Point `web/index.html` at that Gist and deploy to GitHub Pages.

### Calendar Sync

Set these GitHub Actions secrets:

| Secret | Description |
| :--- | :--- |
| `SIMKL_CLIENT_ID` | Simkl API client ID |
| `SIMKL_ACCESS_TOKEN` | Simkl OAuth access token |
| `GIST_ID` | GitHub Gist ID for the `.ics` output |
| `GH_PAT_TOKEN` | GitHub PAT with gist scope |

The workflow runs automatically every Monday at midnight UTC.

---

## 📧 Contact

**Emin Hadžiabdić** — [GitHub @ehadziabdic](https://github.com/ehadziabdic)