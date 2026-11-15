"""The notebook's scraping functions, used EXACTLY as written (copied verbatim, no edits).

Only the small block above the BEGIN marker is new: it gives the functions the names they expect
(`requests`, `BeautifulSoup`) and puts a safety net around network calls, because the notebook
code has no timeouts and `get_wicket_lost_and_runs` loops forever when a page comes back empty.
Everything below the marker must stay byte-for-byte identical to the notebook.
"""
import contextvars
import threading
import time

import requests as _requests
from bs4 import BeautifulSoup  # noqa: F401  (used by the notebook functions)

MAX_REQUESTS = 10            # one scrape needs a single page load
HTTP_TIMEOUT = 10
_budget = contextvars.ContextVar("crex_budget", default=None)
_lock = threading.Lock()


class BudgetExceeded(Exception):
    """Raised inside the notebook functions when a scrape takes too long / asks for too many pages."""


class _GuardedRequests:
    """Drop-in for the `requests` module as the notebook uses it (`requests.get(url).text`)."""

    @staticmethod
    def get(url, **kw):
        if not str(url).startswith("https://crex.com/"):
            raise BudgetExceeded("blocked non-CREX URL")
        b = _budget.get()
        if b is not None:
            with _lock:
                b["n"] += 1
                if b["n"] > MAX_REQUESTS or time.time() > b["deadline"]:
                    raise BudgetExceeded("scrape budget exceeded")
        kw.setdefault("timeout", HTTP_TIMEOUT)
        return _requests.get(url, **kw)


requests = _GuardedRequests()

# ======================= BEGIN VERBATIM NOTEBOOK FUNCTIONS (do not edit) =======================
def get_team_names(soup):
    team_full_names = soup.find_all("div", class_="form-team-name")
    team_short_names = soup.select(".team-details .team-name")[:2]
    full_names = []
    short_names = []
    for team_full_name, team_short_name in zip(team_full_names, team_short_names):
        full_names.append(team_full_name.text.strip())
        short_names.append(team_short_name.text.strip())
    return full_names, short_names

def get_rf_details(soup, short_names):
    rf_matches = soup.find_all("div", class_="format-match-exp")

    team1_rf_matches, team2_rf_matches = (
        rf_matches[0].find_all("div", class_="form-team-detail"),
        rf_matches[1].find_all("div", class_="form-team-detail")
    )

    team1_rr, team2_rr = 0, 0

    team1_rf_runs, team2_rf_runs = [], []
    team1_rf_wickets, team2_rf_wickets = [], []

    try:
        for team1_detail in team1_rf_matches:

            if team1_detail.find("img", alt=short_names[0]):

                team1_score = team1_detail.find("div", class_="team-score").text.strip()
                team1_over = team1_detail.find("div", class_="team-over").text.strip()

                if team1_over != "20.0":
                    over, ball = team1_over.split(".")
                    runs, wickets = team1_score.split("/")

                    team1_rr += int(runs) / (int(over) + int(ball) / 6)

                    team1_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team1_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

                elif team1_over == "20.0":
                    over, ball = team1_over.split(".")
                    runs, wickets = team1_score.split("/")

                    team1_rr += int(runs) / (int(over) + int(ball) / 6)

                    team1_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team1_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

            else:
                team2_score = team1_detail.find("div", class_="team-score").text.strip()
                team2_over = team1_detail.find("div", class_="team-over").text.strip()

                if team2_over != "20.0":
                    over, ball = team2_over.split(".")
                    runs, wickets = team2_score.split("/")

                    team2_rr += int(runs) / (int(over) + int(ball) / 6)

                    team2_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team2_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

                elif team2_over == "20.0":
                    over, ball = team2_over.split(".")
                    runs, wickets = team2_score.split("/")

                    team2_rr += int(runs) / (int(over) + int(ball) / 6)

                    team2_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team2_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

        team1_nrr = round(team1_rr / 5 - team2_rr / 5, 3)

        team1_rr, team2_rr = 0, 0

        for team2_detail in team2_rf_matches:

            if team2_detail.find("img", alt=short_names[1]):

                team2_score = team2_detail.find("div", class_="team-score").text.strip()
                team2_over = team2_detail.find("div", class_="team-over").text.strip()

                if team2_over != "20.0":
                    over, ball = team2_over.split(".")
                    runs, wickets = team2_score.split("/")

                    team2_rr += int(runs) / (int(over) + int(ball) / 6)

                    team2_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team2_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

                elif team2_over == "20.0":
                    over, ball = team2_over.split(".")
                    runs, wickets = team2_score.split("/")

                    team2_rr += int(runs) / (int(over) + int(ball) / 6)

                    team2_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team2_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

            else:
                team1_score = team2_detail.find("div", class_="team-score").text.strip()
                team1_over = team2_detail.find("div", class_="team-over").text.strip()

                if team1_over != "20.0":
                    over, ball = team1_over.split(".")
                    runs, wickets = team1_score.split("/")

                    team1_rr += int(runs) / (int(over) + int(ball) / 6)

                    team1_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team1_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

                elif team1_over == "20.0":
                    over, ball = team1_over.split(".")
                    runs, wickets = team1_score.split("/")

                    team1_rr += int(runs) / (int(over) + int(ball) / 6)

                    team1_rf_runs.append(
                        int(float(int(runs) / (int(over) + int(ball) / 6)) * 20)
                    )

                    team1_rf_wickets.append(
                        int(int(wickets) / (int(over) + int(ball) / 6) * 20)
                        if int(int(wickets) / (int(over) + int(ball) / 6) * 20) <= 10
                        else 10
                    )

        team2_nrr = round(team2_rr / 5 - team1_rr / 5, 3)

        team1_rf_avg_runs = int(sum(team1_rf_runs[:5]) / 5)
        team2_rf_avg_runs = int(sum(team2_rf_runs[:5]) / 5)

        team1_rf_avg_wickets = int(sum(team1_rf_wickets[:5]) / 5)
        team2_rf_avg_wickets = int(sum(team2_rf_wickets[:5]) / 5)

    except ValueError:

        team1_nrr = None
        team2_nrr = None

        team1_rf_avg_runs = None
        team2_rf_avg_runs = None

        team1_rf_avg_wickets = None
        team2_rf_avg_wickets = None

    return team1_nrr, team2_nrr, team1_rf_avg_runs, team2_rf_avg_runs, team1_rf_avg_wickets, team2_rf_avg_wickets


def get_recent_form(script, team1_name=None, team2_name=None):
    index = script.find("tf:") + 3
    modi_script = script[index:]
    last_index = modi_script.find(",")
    rf_line = modi_script[:last_index]
    # print("rf line: ", rf_line)

    t1_rf, t2_rf = rf_line.split("-")

    rf_1 = []
    rf_2 = []
    for i in range(len(t1_rf)):
        curr_word = t1_rf[i]
        if "W" == curr_word:
            n = t1_rf[i + 1]
            for j in range(int(n)):
                rf_1.append(1)

        if "L" == curr_word:
            n = t1_rf[i + 1]
            for j in range(int(n)):
                rf_1.append(0)

        if "T" == curr_word:
            n = t1_rf[i + 1]
            for j in range(int(n)):
                rf_1.append(0.5)


    for i in range(len(t2_rf)):
        curr_word = t2_rf[i]
        if "W" == curr_word:
            n = t2_rf[i + 1]
            for j in range(int(n)):
                rf_2.append(1)

        if "L" == curr_word:
            n = t2_rf[i + 1]
            for j in range(int(n)):
                rf_2.append(0)

        if "T" == curr_word:
            n = t2_rf[i + 1]
            for j in range(int(n)):
                rf_2.append(0.5)

    rev_rf_1 = rf_1[::-1]
    rev_rf_2 = rf_2[::-1]

    final_rf = {
        team1_name: rev_rf_1,
        team2_name: rev_rf_2
    }

    print(f"{team1_name} Recent Form: ", rev_rf_1)
    print(f"{team2_name} Recent Form: ", rev_rf_2)
    print("\n")

    return final_rf


def get_h2h_winner(script):
    index = script.find("https:stats.crickapi.comlivegetPreLiveStats:") + 48
    last_index = script[index:].find("]") + 1
    modi_script = script[index:index + last_index]

    result_index = modi_script.find("result:")
    match = {}
    i = 1
    while result_index != -1:
        result_last_index = modi_script[result_index + 7:].find(",")
        result = modi_script[result_index + 7: result_index + result_last_index + 7]
        if result == "Match Tie":
            match[f"Match {i}"] = result
            print(f"Match {i}: ", match[f"Match {i}"])
            result_index = modi_script.find("result:", result_index + 1 + 7)
        else:
            if "won" in result:
                winner, raw = result.split("won")
            elif "Won" in result:
                winner, raw = result.split("Won")
            result_index = modi_script.find("result:", result_index + 1 + 7)
            match[f"Match {i}"] = winner.replace(" ", "")
            print(f"Match {i}: ", match[f"Match {i}"])

        i += 1
    print("\n")

    return match


def get_date_and_time(script):
    date_index = script.find(",t:") + 3
    date_last_index = script[date_index:].find(",")
    date_and_time = script[date_index: date_index + date_last_index]

    date_month_year, time = date_and_time.split("T")
    year, month, date = date_month_year.split("-")
    time = time[:5]

    print("Date: ", date)
    print("Month: ", month)
    print("Year: ", year)
    print("Time: ", time)
    print("\n")

    return date, month, year, time
# ======================== END VERBATIM NOTEBOOK FUNCTIONS ========================
