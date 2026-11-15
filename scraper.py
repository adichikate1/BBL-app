"""Fetch the five model inputs for a match from CREX using only its match code.

This module is just the glue. All parsing is done by the notebook functions in crex_functions.py, used exactly
as written: get_team_names + get_rf_details read the match page itself (team names, last-5 NRR, average runs
and wickets), get_recent_form / get_h2h_winner / get_date_and_time read its embedded data. One page load per match.
"""
import datetime
import re
import threading
import time

import requests as _rq

import crex_functions as cf
from crex_functions import (BeautifulSoup, get_date_and_time, get_h2h_winner, get_recent_form,  # noqa: F401
                            get_rf_details, get_team_names, requests)

# The slug text is ignored by CREX; only the code matters (the notebook relies on this too).
URL = ("https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025"
       "-match-updates-{code}/match-details")
CODE_RE = re.compile(r"^[A-Za-z0-9]{2,8}$")
CACHE_TTL = 600
SCRAPE_SECONDS = 30          # hard cap per scrape (a scrape is one page load now)
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


def _rf_both(soup, short_names):
    """get_rf_details, called exactly as written, for both teams.

    As written it reads team 2's average runs/wickets from the wrong list (it takes the first five entries, which
    are team 1's opponents). Its team-1 outputs are right, so call it a second time with the two recent-form blocks
    swapped and read team 2's numbers from that call's team-1 outputs. Returns (nrr, avg_runs, avg_wickets) per team.
    """
    blocks = soup.find_all("div", class_="format-match-exp")
    if len(blocks) < 2 or any(len(x.find_all("div", class_="form-team-detail")) != 10 for x in blocks[:2]):
        raise ScrapeError("Could not read the recent form: CREX needs 5 earlier matches for each team.")
    n1, _n2, r1, _r2, w1, _w2 = get_rf_details(soup, short_names)
    swapped = BeautifulSoup(str(blocks[1]) + str(blocks[0]), "html.parser")
    n2, _n1, r2, _r1, w2, _w1 = get_rf_details(swapped, [short_names[1], short_names[0]])
    if None in (n1, n2, r1, r2, w1, w2):
        raise ScrapeError("Could not read the recent-form scores from CREX (unexpected score format).")
    return (n1, r1, w1), (n2, r2, w2)


def _scrape(code):
    url = URL.format(code=code)
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    script = str(soup.find("script", {"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")
    if len(script) < 500:
        raise ScrapeError(f"Match code '{code}' was not found on CREX.")

    full_names, short_names = get_team_names(soup)
    if len(full_names) != 2 or len(short_names) != 2:
        raise ScrapeError("Could not read the team names from CREX.")
    team1_name, team2_name = full_names
    team1_short_name, team2_short_name = short_names
    recent_form = get_recent_form(script, team1_name, team2_name)
    h2h_winner = get_h2h_winner(script)
    match_date, match_time = _match_date_time(script)
    (t1_nrr, t1_runs, t1_wk), (t2_nrr, t2_runs, t2_wk) = _rf_both(soup, short_names)

    h2h_t1, h2h_t2, h2h_unmatched = _h2h_wins(h2h_winner, team1_name, team1_short_name, team2_name, team2_short_name)
    return {
        "h2h_results": [str(v) for v in list(h2h_winner.values())[:5]], "h2h_unmatched": h2h_unmatched,
        "code": code, "team1_name": team1_name, "team2_name": team2_name,
        "date": match_date, "time": match_time,
        "t1": {"form": float(sum(recent_form[team1_name][:5])), "h2h": h2h_t1,
               "nrr5": round(t1_nrr, 4), "avgruns": round(t1_runs, 2), "avgwk": round(t1_wk, 2)},
        "t2": {"form": float(sum(recent_form[team2_name][:5])), "h2h": h2h_t2,
               "nrr5": round(t2_nrr, 4), "avgruns": round(t2_runs, 2), "avgwk": round(t2_wk, 2)},
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
