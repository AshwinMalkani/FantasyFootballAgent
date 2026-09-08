# Fantasy Hub

One dashboard for all of your fantasy football teams across **Sleeper**, **ESPN**, and **Yahoo**:
every roster, this week's matchup, suggested lineup changes, and ranked waiver-wire pickups.

- `backend/` – FastAPI. Pulls each platform, normalizes it, and runs a deterministic
  lineup optimizer + waiver ranker on Sleeper's weekly projections.
- `frontend/` – Vite + React + Tailwind dashboard.
- `legacy/` – the original single-league Sleeper prototype (reference only).

## Run it

```bash
# backend
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env           # then fill it in (see below)
./.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

The first request downloads Sleeper's player database (~14 MB) and this week's projections;
both are cached under `backend/.cache/`. Use the **Refresh** button (or `POST /api/refresh`)
to clear caches.

## Credentials (`backend/.env`)

### Sleeper
No auth needed. Set `SLEEPER_USERNAME` to your Sleeper username. All of your leagues for the
current season are picked up automatically.

### ESPN (private league)
1. `ESPN_LEAGUE_ID` – from the league URL: `fantasy.espn.com/football/team?leagueId=XXXXXX`.
2. While logged in at fantasy.espn.com, open DevTools → **Application** → **Cookies** →
   `https://fantasy.espn.com` and copy:
   - `espn_s2` → `ESPN_S2`
   - `SWID` → `ESPN_SWID` (keep the curly braces)
3. Your team is matched by SWID. If that fails, set `ESPN_TEAM_ID` (`teamId=` in the URL).

Cookies last roughly a year; when they expire the ESPN card on the dashboard tells you.

### Yahoo (OAuth app, one-time)
1. Go to https://developer.yahoo.com/apps/create and create an app:
   - Application type: **Installed Application**
   - Redirect URI: `oob` (or `https://localhost`)
   - API permissions: **Fantasy Sports – Read**
2. Create `backend/oauth2.json`:
   ```json
   {"consumer_key": "YOUR_CLIENT_ID", "consumer_secret": "YOUR_CLIENT_SECRET"}
   ```
3. Run the one-time authorization from `backend/`:
   ```bash
   ./.venv/bin/python -c "from yahoo_oauth import OAuth2; OAuth2(None, None, from_file='oauth2.json')"
   ```
   A browser opens; approve, paste the code back into the terminal. Tokens are written into
   `oauth2.json` and refreshed automatically after that.
4. Optional: `YAHOO_LEAGUE_ID` (the number in `football.fantasysports.yahoo.com/f1/NNNNNN`) if you
   are in more than one Yahoo league.

## How projections and recommendations work

- **Projections** come from Sleeper's weekly projection feed. For Sleeper leagues the stat-line
  projection is scored with that league's exact `scoring_settings`. ESPN leagues use ESPN's own
  league-scored projections. Yahoo leagues use Sleeper's PPR / half-PPR / standard totals matched to
  the league's reception scoring (approximate).
- **Cross-platform player mapping** uses the `espn_id` / `yahoo_id` fields in Sleeper's player DB,
  with a name+position fallback.
- **Lineup optimizer**: players on bye or OUT/IR/Doubtful count as 0; dedicated slots are filled
  first, then FLEX / SUPER_FLEX. Swaps worth less than 0.5 points are ignored.
- **Waiver ranker**: `score = lineup gain + position-weighted depth value + min(5, log10(1 + Sleeper trending adds))`, with
  a suggested drop (lowest-projected bench player at the same position, never someone on bye).

## Live page (game days)

The **Live** tab polls every 30 seconds and shows every rostered player across all leagues with
their game status, live stat line (Sleeper, refreshed every 30s), points in each league, and the
latest ESPN play-by-play lines that mention them. The right-hand feed lists point changes since the
last poll and scoring plays. To preview it outside of game time:
`http://localhost:5173/activity?season=2025&week=1&date=20250907`.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/state` | current season and week |
| `GET /api/leagues` | summaries for every configured league (errors inlined per league) |
| `GET /api/leagues/{platform}/{id}` | roster, slot template, scoring |
| `GET /api/leagues/{platform}/{id}/lineup` | current vs suggested starters and moves |
| `GET /api/leagues/{platform}/{id}/waivers` | ranked free agents with suggested drops |
| `GET /api/activity?bench=false` | game-day view: my players across leagues with live stats, plays, per-league points, and a change feed (add `season`, `week`, `date=YYYYMMDD` to replay a past week) |
| `POST /api/refresh` | clear all caches |

## Tests

```bash
cd backend && ./.venv/bin/python -m pytest
```

## Roadmap
- Trade analyzer (rest-of-season value from remaining-week projections)
- Optional LLM "explain these moves" layer
- Exact Yahoo scoring via stat modifiers
- Deployment (Render / Fly)
