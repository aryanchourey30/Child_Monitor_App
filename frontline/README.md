# GuardianBaby Frontline

Frontline is a separate React + TypeScript + Vite frontend for GuardianBaby backend monitoring.

## What It Does
- Live Monitoring Dashboard page
- History & Analytics page
- Polls backend APIs and renders latest status, scene summary, alerts, events, sessions, and simple analytics
- Uses live per-frame analysis (`latest-state.frame_result` / `latest-state.live_analysis`) for real-time dashboard sections

## Pages
1. `Dashboard`
- latest frame panel
- status cards
- scene summary + risk reason
- observations
- recommended action
- live alert banner for high/critical risk or important activity (`near_edge`, `restless`, `unsafe_exploration`)
- recent alerts
- recent frame strip
- session summary mini panel

2. `History & Analytics`
- filters (risk, visibility, activity, time range)
- event table + detail modal
- session summaries
- simple risk/activity distribution bars
- CSV and JSON export actions

## Configure Backend URL
Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Set:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Install and Run

```bash
npm install
npm run dev
```

Build production bundle:

```bash
npm run build
npm run preview
```

## Expected Backend APIs
- `GET /health`
- `GET /latest-state`
- `GET /events?limit=...`
- `GET /events/{id}`
- `GET /sessions`
- `GET /sessions/{id}`
- `GET /latest-frame`
- `GET /recent-frames?limit=...`
- `GET /media/<relative-data-path>` for frames/snapshots served from backend `data/`

## Notes
- Frontline is intentionally separated under `guardian_baby/frontline`.
- Frontline uses an adapter layer (`src/api/adapters.ts`) to normalize backend payloads into stable UI models.
- If `/recent-frames` is empty, recent frames are derived from `latest-state` and `events`.
