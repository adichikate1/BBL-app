"""Fetch the five model inputs for a match from CREX using only its match code.

This module is just the glue. All parsing is done by the notebook functions in crex_functions.py,
which are used exactly as written (find_team_name, get_recent_form, get_h2h_winner, get_links,
get_wicket_lost_and_runs), called in the same order as in the notebook, and the averages use the
notebook's own formulas (mean of the last 5 matches).
"""
import contextvars
import datetime
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests as _rq

import crex_functions as cf
from crex_functions import (BeautifulSoup, find_team_name, get_date_and_time, get_h2h_winner,  # noqa: F401
                            get_links, get_recent_form, get_wicket_lost_and_runs, requests)

# The slug text is ignored by CREX; only the code matters (the notebook relies on this too).
URL = ("https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025"
       "-match-updates-{code}/match-details")
CODE_RE = re.compile(r"^[A-Za-z0-9]{2,8}$")
CACHE_TTL = 600
SCRAPE_SECONDS = 50          # hard cap per scrape (gunicorn worker timeout is 60)
_cache, _lock = {}, threading.Lock()


class ScrapeError(Exception):
    """Something went wrong while reading CREX (message is safe to show to the user)."""


class InvalidCode(ScrapeError):
    pass


def _norm(s):
    return re.sub(r"\W+", "", s or "").lower()


def _keys(name, short):
    """Every spelling CREX may use for a team in a result line: full name, name without 'Women', short code."""
    full = _norm(name)
    keys = {full, full.replace("women", ""), _norm(short)}
    sh = _norm(short)
    if len(sh) > 2 and sh.endswith("w"):
        keys.add(sh[:-1])                       # 'BH-W' -> 'bh'
    return {k for k in keys if k}


def _is_team(winner, name, short):
    w = _norm(winner)
    if not w:
        return False
    for k in _keys(name, short):
        if w == k or (len(k) >= 4 and len(w) >= 4 and (w.startswith(k) or k.startswith(w))):
            return True
    return False


def _h2h_wins(h2h_winner, t1, s1, t2, s2):
    """Wins per team over the last 5 head-to-head results. Ties/no-result count for nobody.
    Returns (t1_wins, t2_wins, unmatched_winner_texts)."""
    a = b = 0
    unmatched = []
    for v in list(h2h_winner.values())[:5]:      # the model feature is 'Last 5 H2H Won'
        if _norm(v) == "matchtie":
            continue
        ia, ib = _is_team(v, t1, s1), _is_team(v, t2, s2)
        if ia and not ib:
            a += 1
        elif ib and not ia:
            b += 1
        else:
            unmatched.append(v)
    return a, b, unmatched


def _match_date_time(script):
    """Run the notebook's get_date_and_time. A date problem must not break the whole fetch."""
    try:
        date, month, year, time_ = get_date_and_time(script)
        iso = datetime.date(int(year), int(month), int(date)).isoformat()
        return iso, (time_ if re.fullmatch(r"\d{2}:\d{2}", time_) else None)
    except Exception:  # noqa: BLE001 - page layout changed / no date on the page
        return None, None


def _scrape(code):
    # --- main match page (same lines as the notebook) ---
    url = URL.format(code=code)
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    script = str(soup.find("script", {"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")
    if len(script) < 500:
        raise ScrapeError(f"Match code '{code}' was not found on CREX.")

    team1_name, team1_short_name, team2_name, team2_short_name = find_team_name(script)
    recent_form = get_recent_form(script, team1_name, team2_name)
    h2h_winner = get_h2h_winner(script)
    team1_all_match_links, team2_all_match_links = get_links(script)
    match_date, match_time = _match_date_time(script)

    # the two teams are independent, so read them side by side (each keeps the notebook's own code path)
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(contextvars.copy_context().run, get_wicket_lost_and_runs, team1_all_match_links, team1_short_name)
        f2 = ex.submit(contextvars.copy_context().run, get_wicket_lost_and_runs, team2_all_match_links, team2_short_name)
        all_team1_wickets_runs, all_team1_nrr = f1.result()
        all_team2_wickets_runs, all_team2_nrr = f2.result()

    # --- averages: the notebook's own formulas ---
    team1_avg_runs = (all_team1_wickets_runs["Match 1"][team1_short_name]["Total Runs"] + all_team1_wickets_runs["Match 2"][team1_short_name]["Total Runs"] + all_team1_wickets_runs["Match 3"][team1_short_name]["Total Runs"] + all_team1_wickets_runs["Match 4"][team1_short_name]["Total Runs"] + all_team1_wickets_runs["Match 5"][team1_short_name]["Total Runs"])/5
    team2_avg_runs = (all_team2_wickets_runs["Match 1"][team2_short_name]["Total Runs"] + all_team2_wickets_runs["Match 2"][team2_short_name]["Total Runs"] + all_team2_wickets_runs["Match 3"][team2_short_name]["Total Runs"] + all_team2_wickets_runs["Match 4"][team2_short_name]["Total Runs"] + all_team2_wickets_runs["Match 5"][team2_short_name]["Total Runs"])/5
    team1_avg_wickets = (all_team1_wickets_runs["Match 1"][team1_short_name]["Total Wickets"] + all_team1_wickets_runs["Match 2"][team1_short_name]["Total Wickets"] + all_team1_wickets_runs["Match 3"][team1_short_name]["Total Wickets"] + all_team1_wickets_runs["Match 4"][team1_short_name]["Total Wickets"] + all_team1_wickets_runs["Match 5"][team1_short_name]["Total Wickets"])/5
    team2_avg_wickets = (all_team2_wickets_runs["Match 1"][team2_short_name]["Total Wickets"] + all_team2_wickets_runs["Match 2"][team2_short_name]["Total Wickets"] + all_team2_wickets_runs["Match 3"][team2_short_name]["Total Wickets"] + all_team2_wickets_runs["Match 4"][team2_short_name]["Total Wickets"] + all_team2_wickets_runs["Match 5"][team2_short_name]["Total Wickets"])/5
    team1_nrr5 = (all_team1_nrr["Match 1"] + all_team1_nrr["Match 2"] + all_team1_nrr["Match 3"] + all_team1_nrr["Match 4"] + all_team1_nrr["Match 5"])/5
    team2_nrr5 = (all_team2_nrr["Match 1"] + all_team2_nrr["Match 2"] + all_team2_nrr["Match 3"] + all_team2_nrr["Match 4"] + all_team2_nrr["Match 5"])/5

    h2h_t1, h2h_t2, h2h_unmatched = _h2h_wins(h2h_winner, team1_name, team1_short_name, team2_name, team2_short_name)
    return {
        "h2h_results": [str(v) for v in list(h2h_winner.values())[:5]], "h2h_unmatched": h2h_unmatched,
        "code": code, "team1_name": team1_name, "team2_name": team2_name,
        "date": match_date, "time": match_time,
        "t1": {"form": float(sum(recent_form[team1_name][:5])), "h2h": h2h_t1,
               "nrr5": round(team1_nrr5, 4), "avgruns": round(team1_avg_runs, 2), "avgwk": round(team1_avg_wickets, 2)},
        "t2": {"form": float(sum(recent_form[team2_name][:5])), "h2h": h2h_t2,
               "nrr5": round(team2_nrr5, 4), "avgruns": round(team2_avg_runs, 2), "avgwk": round(team2_avg_wickets, 2)},
        "matches_used": {"t1": 5, "t2": 5},
    }


def fetch_match(code):
    code = (code or "").strip()
    if not CODE_RE.match(code):
        raise InvalidCode("Enter the CREX match code (letters/numbers only, e.g. PZ7).")
    now = time.time()
    with _lock:
        hit = _cache.get(code)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    token = cf._budget.set({"n": 0, "deadline": now + SCRAPE_SECONDS})
    try:
        data = _scrape(code)
    except ScrapeError:
        raise
    except cf.BudgetExceeded as e:
        raise ScrapeError("CREX is responding too slowly or a past match page is missing. Please try again later.") from e
    except _rq.RequestException as e:
        raise ScrapeError("Could not reach CREX right now. Please try again in a moment.") from e
    except (IndexError, KeyError, ValueError, TypeError, AttributeError, NameError, ZeroDivisionError) as e:
        raise ScrapeError("Could not read this match from CREX. It needs 5 earlier matches for each team, "
                          "and the page format must be unchanged.") from e
    finally:
        cf._budget.reset(token)
    with _lock:
        if len(_cache) >= 128:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[code] = (now, data)
    return data
