# BBL Women · Match Predictor

Flask web app that predicts the winner of a Big Bash League Women match from five Team 1 − Team 2 differences
(recent form, head-to-head, last-5 net run rate, average runs, average wickets).

**Model:** symmetric logistic regression (no intercept; every training match is also flipped), trained on 190 matches (2022–2025).
Leave-one-season-out accuracy: 2023 50.0%, 2024 65.0%, 2025 64.1% → **58.4% overall** (137 matches; always-one-side baseline ≈ 53%).
It is only modestly better than chance — treat it as an educational tool, not for betting.

## Run locally
```bash
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000
# production-style:
gunicorn app:app --workers 2 --threads 4 --bind 0.0.0.0:8000
```

## Deploy
- **Render:** push this folder to GitHub → New → Blueprint (uses `render.yaml`, Python 3.11.9, health check `/healthz`).
- **Docker:** `docker build -t bbl . && docker run -p 8000:8000 bbl`
- **Heroku/Railway-style:** `Procfile` is included.

Env vars (optional): `PORT`, `LOG_LEVEL` (INFO), `RATE_LIMIT` (requests/min/IP, default 60).

## API
| Route | Method | Notes |
|---|---|---|
| `/healthz` | GET | liveness |
| `/api/teams` | GET | teams, features, validation stats |
| `/api/defaults?team1=..&team2=..` | GET | latest known stats for the pair |
| `/api/fetch?code=PZ7` | GET | scrapes CREX for that match code → both teams + all 5 stats (10 req/min/IP, cached 10 min) |
| `/api/predict` | POST | `{team1, team2, t1:{form,h2h,nrr5,avgruns,avgwk}, t2:{...}}` → probabilities + per-feature effects |

## Auto-fill from a CREX match code
Type a CREX match code (e.g. `PZ7`) and press **Fetch & predict**. `scraper.py` calls the notebook's own functions, unchanged and
in the notebook's order: `find_team_name` → `get_recent_form` → `get_h2h_winner` → `get_links` → `get_wicket_lost_and_runs`
(per team), then the notebook's averaging formulas (mean of the last 5 matches).

- `crex_functions.py` holds those functions **verbatim**. Only the block above its BEGIN marker is new: it gives them a
  `requests` with a 10 s timeout, a per-scrape cap (60 page loads / 50 s — the notebook loops forever on an empty page) and a
  "crex.com URLs only" check. To change scraping, replace the functions below the marker with your updated notebook versions.
- Each team needs 5 earlier matches on CREX; otherwise the site says so and you can type the numbers by hand.
- A cold fetch loads ~21 pages (≈10–25 s); results are cached 10 min. Limit: `FETCH_LIMIT` (default 10/min/IP). The notebook
  functions `print` their progress to the server log.
- It scrapes a third-party site: check CREX's terms; some hosting IPs may be blocked, and a layout change will break it.

## Bet tracker (`/tracker`)
Log every match as **won / lost / pending / skipped**; the page keeps net profit-loss, win rate, ROI and a running total per match.
- **Profit target rule:** `net loss ÷ (matches won − matches lost)`. Negative result (more lost than won) → that amount is the profit to aim for in the next match; positive result (more won than lost) → base target (₹100); no loss yet → base target; won = lost → base target (cannot divide). The page also shows the stake that would earn that profit at your expected odds.
- "Played" counts only won + lost bets. Skipped and pending matches are logged but not counted in the divisor.
- Optional **max stake** cap and **stop-loss** warning, plus an honest "if it wins / if it loses at odds X" preview.
- The predictor shows the suggested stake under each prediction (and flags toss-ups as skippable) with a "Log this bet" link that pre-fills the tracker.
- Data lives only in the visitor's browser (localStorage, never sent to the server); use **Export CSV** to keep a copy.
- Logic is in `static/ledger.js` (unit tests: `node tests/ledger.test.js`).

## Re-train / test
```bash
pip install -r requirements-train.txt && python train_model.py data/bbl_women.csv   # rewrites model/*.json
pip install -r requirements-dev.txt && pytest -q
```
The server needs only Flask, gunicorn, requests and beautifulsoup4: the trained weights are plain JSON, so no scikit-learn at runtime.

Notes: the rate limiter is in-memory per worker (fine for a small site; use a shared store for many instances).
Team stats are pre-filled from each team's most recent match in the CSV — update the CSV and re-train to refresh them.

## Bet tracker (`/tracker`)

A profit/loss log that lives in the browser (`localStorage`, key `bblw.ledger.v1`). No server storage.

- Every match gets one row: date, match, pick, status (`pending`, `won`, `lost`, `skipped`), stake, amount, note.
- Net profit/loss = sum of won amounts minus lost amounts. Skipped and pending rows are kept but not counted.
- **Profit target** = `net loss ÷ (won − lost)`, rounded. Negative result -> that is the profit to aim for; positive result, no loss, or won = lost -> base target (default ₹100). Skipped/pending are not counted.
  Examples: ₹300 down, 4 won 6 lost -> 300 ÷ (−2) -> target ₹150; ₹360 down, 6 won 4 lost -> positive -> target ₹100.
- Under it the page shows the stake needed to win that profit at your odds (`target ÷ (odds − 1)`), capped by your max stake, with the net after a win or a loss.
- Export CSV / Clear all. Clearing site data deletes the log, so export regularly.
- Pure maths lives in `static/ledger.js` and is tested with `node tests/ledger.test.js`.

Note: this formula does not recover losses by itself; it is a staking rule, not an edge.

### Auto-fill and GitHub backup (tracker)

- **CREX code on the tracker:** type the match code and press *Fetch match*. Date and time come from the notebook function `get_date_and_time` (used verbatim in `crex_functions.py`), the match name from the team names, and *My pick* from the model's prediction (its probability is saved too). Status, stake, amount and note are yours to fill. Time is shown exactly as CREX gives it.
- **Several matches a day:** each match is its own row (date + time, own CREX code). The same code cannot be added twice; the date stays after *Add match* so the second match of the day is quick.
- **GitHub backup (PyGithub, `github_store.py`):** every change is committed to `data/ledger.json`. Set these environment variables on the server:

| Variable | Meaning |
|---|---|
| `GITHUB_TOKEN` | fine-grained token, only this repo, *Contents: read & write* |
| `GITHUB_REPO` | `owner/name` |
| `SYNC_KEY` | secret you type once into the tracker's "GitHub backup" box (protects your repo from strangers) |
| `GITHUB_BRANCH`, `GITHUB_LEDGER_PATH` | optional (default branch, `data/ledger.json`) |

The token never reaches the browser. Without these variables the backup box stays hidden and the tracker works locally. Use HTTPS in production because the sync key travels in a header. An empty ledger is never pushed unless you delete the last match / press *Clear all* / confirm an empty *Sync now*.
