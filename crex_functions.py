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

MAX_REQUESTS = 60            # one scrape needs ~21 page loads
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
def find_team_name(script,flag="Yes"):
    correct_team1_name_index = script.find("team1:") + 6
    correct_team1_name_last_index = script[correct_team1_name_index:].find(",")
    correct_team1_name = script[correct_team1_name_index: correct_team1_name_index + correct_team1_name_last_index]

    correct_team2_name_index = script.find("team2:") + 6
    correct_team2_name_last_index = script[correct_team2_name_index:].find(",")
    correct_team2_name = script[correct_team2_name_index: correct_team2_name_index + correct_team2_name_last_index]

    script_index = script.find("https:api.goscorer.comapiv3getSV3")
    modi_script = script[script_index:]

    team1_short_name_index = modi_script.find("team1:") + 6
    team1_short_name_last_index = modi_script[team1_short_name_index:].find(",")
    team1_short_name = modi_script[team1_short_name_index: team1_short_name_index + team1_short_name_last_index]

    team2_short_name_index = modi_script.find("team2:") + 6
    team2_short_name_last_index = modi_script[team2_short_name_index:].find(",")
    team2_short_name = modi_script[team2_short_name_index:team2_short_name_index + team2_short_name_last_index]

    team1_name_index = modi_script.find("team1_f_n:") + 10
    team1_name_last_index = modi_script[team1_name_index:].find(",")
    team1_name = modi_script[team1_name_index: team1_name_index + team1_name_last_index]

    team2_name_index = modi_script.find("team2_f_n:") + 10
    team2_name_last_index = modi_script[team2_name_index:].find(",")
    team2_name = modi_script[team2_name_index:team2_name_index + team2_name_last_index]

   
    if team1_name == "null" and team2_name == "null":
        team1_short_name_index = modi_script.find("team1short:") + 11
        team1_short_name_last_index = modi_script[team1_short_name_index:].find(",")
        team1_short_name = modi_script[team1_short_name_index: team1_short_name_index + team1_short_name_last_index]

        team2_short_name_index = modi_script.find("team2short:") + 11
        team2_short_name_last_index = modi_script[team2_short_name_index:].find(",")
        team2_short_name = modi_script[team2_short_name_index:team2_short_name_index + team2_short_name_last_index]

        team1_name_index = modi_script.find("team1:") + 6
        team1_name_last_index = modi_script[team1_name_index:].find(",")
        team1_name = modi_script[team1_name_index: team1_name_index + team1_name_last_index]

        team2_name_index = modi_script.find("team2:") + 6
        team2_name_last_index = modi_script[team2_name_index:].find(",")
        team2_name = modi_script[team2_name_index:team2_name_index + team2_name_last_index]
    

    if flag == "Yes":
        temp = None
        if correct_team1_name != team1_name:
            team1_name = correct_team1_name
            team2_name = correct_team2_name

            temp = team1_short_name
            team1_short_name = team2_short_name
            team2_short_name = temp

    print("Team 1 Name: ", team1_name)
    print("Team 2 Name: ", team2_name)
    print("Team 1 Short Name: ", team1_short_name)
    print("Team 2 Short Name: ", team2_short_name)
    print("\n")

    return [team1_name,team1_short_name,team2_name,team2_short_name]


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
                winner = winner.replace("-", "")
            elif "Won" in result:
                winner, raw = result.split("Won")
                winner = winner.replace("-", "")
            result_index = modi_script.find("result:", result_index + 1 + 7)
            match[f"Match {i}"] = winner.replace(" ", "")
            print(f"Match {i}: ", match[f"Match {i}"])

        i += 1
    print("\n")

    return match


def get_links(script):
    index = script.find(f"https:api.goscorer.comapiv3getIV4?key=") + 3
    last_index = index + 2000
    new_script = script[index: last_index]

    first_t1_index = new_script.find("t1f:") + 4
    last_t1_index = new_script[first_t1_index:].find(",")
    t1_line = new_script[first_t1_index: first_t1_index + last_t1_index] + "|"
    # print(t1_line)

    first_t1_line_index = 0
    last_t1_line_index = 0
    team1_links = []
    team1_codes = []
    while last_t1_line_index != -1:

        if last_t1_line_index == 0:
            last_t1_line_index = t1_line.find("|")
        else:
            last_t1_line_index = t1_line.find("|", last_t1_line_index + 1)

        if last_t1_line_index != -1:
            t1_form = t1_line[first_t1_line_index: last_t1_line_index]
            # print("Hello: ", t1_form)
            result = t1_form.split("-")[-1]
            result = result.replace("^", "")
            result = result.replace("Semi Final ", "")
            result = result.replace("Eliminator", "")
            result = result.replace("Eliminator", "")
            result = result.replace("Qualifier", "")
            result = result.replace("Knockout", "")
            result = result.replace("Final", "")
            print(result)

            
            if result[0] == "2" and result[1] != "2":
                # print("Letter found at index 2: ", result[2])
                match_code = result[1:4]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[1:5]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")

                        match_code = result[1:4]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                            print("226")
                        elif len_ > 500:
                            pass

                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team1_links.append(url)
                team1_codes.append(match_code)

            elif result[2] == "2":
                # print("Letter found at index 2: ", result[2])
                match_code = result[2 + 1:6 + 1]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[2 + 1:5 + 1]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")

                        match_code = result[2 + 1:6 + 1]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                            print("226")
                        elif len_ > 500:
                            pass

                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team1_links.append(url)
                team1_codes.append(match_code)
                
            elif result[1] == "2":
                # print("Digit found at index 2: ", result[2])
                match_code = result[2:6]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[2:5]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")

                        match_code = result[2:6]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                            print(187)
                        elif len_ > 500:
                            pass

                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team1_links.append(url)
                team1_codes.append(match_code)

    team1_all_match_links = {
        "match_5_code": team1_codes[0],
        "match_5": team1_links[0],
        "match_4_code": team1_codes[1],
        "match_4": team1_links[1],
        "match_3_code": team1_codes[2],
        "match_3": team1_links[2],
        "match_2_code": team1_codes[3],
        "match_2": team1_links[3],
        "match_1_code": team1_codes[4],
        "match_1": team1_links[4],
    }




    index = script.find(f"https:api.goscorer.comapiv3getIV4?key=") + 3
    last_index = index + 2000
    new_script = script[index: last_index]

    first_t2f_index = new_script.find("t2f:") + 4
    last_t2f_index = new_script[first_t2f_index:].find(",")
    t2f_line = new_script[first_t2f_index: first_t2f_index + last_t2f_index] + "|"
    # print(t2f_line)

    first_t2f_line_index = 0
    last_t2f_line_index = 0
    team2_links = []
    team2_codes = []
    while last_t2f_line_index != -1:

        if last_t2f_line_index == 0:
            last_t2f_line_index = t2f_line.find("|")
        else:
            last_t2f_line_index = t2f_line.find("|", last_t2f_line_index + 1)

        if last_t2f_line_index != -1:
            t2f_form = t2f_line[first_t2f_line_index: last_t2f_line_index]
            result = t2f_form.split("-")[-1]
            result = result.replace("^", "")
            result = result.replace("Semi Final ", "")
            result = result.replace("Eliminator", "")
            result = result.replace("Eliminator", "")
            result = result.replace("Qualifier", "")
            result = result.replace("Knockout", "")
            result = result.replace("Final", "")
            # print(result)
            print("Modified result: ",result)

            


            if result[0] == "2" and result[1] != "2":
                # print("Letter found at index 2: ", result[2])
                match_code = result[1:5]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[1:4]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")
                        match_code = result[1:5]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                        elif len_ > 500:
                            pass

                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team2_links.append(url)
                team2_codes.append(match_code)

            elif result[2] == "2":
                # print("Letter found at index 2: ", result[2])
                match_code = result[2 + 1:6 + 1]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[2 + 1:5 + 1]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")
                        match_code = result[2 + 1:6 + 1]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                        elif len_ > 500:
                            pass

                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team2_links.append(url)
                team2_codes.append(match_code)
            
            elif result[1] == "2":
                # print("Digit found at index 2: ", result[2])
                match_code = result[2:6]

                url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                len_ = len(match_script)
                if len_ < 500:
                    match_code = result[2:5]
                    url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                    match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                    len_ = len(match_script)
                    if len_ < 500:
                        print(f"Match code: {match_code} is not valid")
                        match_code = result[2:6]
                        url = f"https://crex.com/cricket-live-score/bh-w-vs-mlr-w-1st-t20-womens-big-bash-league-2025-match-updates-{match_code}/match-details"
                        match_script = str(BeautifulSoup(requests.get(url).text, 'html.parser').find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

                        len_ = len(match_script)
                        if len_ < 500:
                            print(f"Match code: {match_code} is not valid")
                            print(311)
                        elif len_ > 500:
                            pass
                    elif len_ > 500:
                        pass
                        #print(f"Match code: {match_code} is valid")
                        #print(f"Match link: {url}")

                elif len_ > 500:
                    pass
                    #print(f"Match code: {match_code} is valid")
                    #print(f"Match link: {url}")

                team2_links.append(url)
                team2_codes.append(match_code)

    team2_all_match_links = {
        "match_5_code": team2_codes[0],
        "match_5": team2_links[0],
        "match_4_code": team2_codes[1],
        "match_4": team2_links[1],
        "match_3_code": team2_codes[2],
        "match_3": team2_links[2],
        "match_2_code": team2_codes[3],
        "match_2": team2_links[3],
        "match_1_code": team2_codes[4],
        "match_1": team2_links[4],
    }

    return team1_all_match_links, team2_all_match_links

def get_wicket_lost_and_runs(match_links, team_short_name):

        len_team_all_match_links = len(match_links)/2
        i = 0
        all_teams_wickets_runs = {}
        all_nrr = {}
        while i < len_team_all_match_links:
            team_match_link = match_links[f"match_{i + 1}"]
            print("match link:", team_match_link)

            team_r = requests.get(team_match_link)
            team_soup = BeautifulSoup(team_r.text, 'html.parser')
            team_script = str(team_soup.find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")

            # with open("wicket error.json", "w", encoding="utf-8") as f:
            #     f.write(team_script)

            while team_script == "None":
                team_r = requests.get(team_match_link)
                team_soup = BeautifulSoup(team_r.text, 'html.parser')
                team_script = str(team_soup.find("script",{"id": "app-root-state"})).replace("&q;", "").replace("&a;", "").replace("/", "")


            


            team1_name_score, team1_short_name_score, team2_name_score, team2_short_name_score = find_team_name(team_script, "No")

            print("Main Team 1: ", team_short_name)
            # print("Main Team 2: ", team2_short_name)
            # print("Winner: ", get_winner(team1_script))
            print("Team 1: ", team1_name_score, team1_short_name_score)
            print("Team 2: ", team2_name_score, team2_short_name_score)
            print("\n")

            all_teams_wickets_runs[f"Match {i + 1}"] = {
                team1_short_name_score: {},
                team2_short_name_score: {}
            }

            # print(f"Match {i + 1}: {team1_short_name_score} vs {team2_short_name_score}")
            if team1_short_name_score == team_short_name:
                team1_score_index = team_script.find("score1:") + 7
                team1_score_last_index = team_script[team1_score_index:].find(",")
                team1_score = team_script[team1_score_index:team1_score_index + team1_score_last_index]

                team1_overs_index = team_script.find("over1:") + 6
                team1_overs_last_index = team_script[team1_overs_index:].find(",")
                team1_overs = team_script[team1_overs_index:team1_overs_index + team1_overs_last_index].replace(")","").replace("(","")

                team2_score_index = team_script.find("score2:") + 7
                team2_score_last_index = team_script[team2_score_index:].find(",")
                team2_score = team_script[team2_score_index:team2_score_index + team2_score_last_index]

                team2_overs_index = team_script.find("over2:") + 6
                team2_overs_last_index = team_script[team2_overs_index:].find(",")
                team2_overs = team_script[team2_overs_index:team2_overs_index + team2_overs_last_index].replace(")","").replace("(","")

                team1_run, team1_wicket = team1_score.split("-")
                team1_run = float(team1_run)
                if "." in team1_overs:
                    team1_over, team1_ball = team1_overs.split(".")
                    if team1_ball != 0:
                        team1_proper_overs = float(team1_over) + (float(team1_ball)/6)
                        team1_rr = team1_run/team1_proper_overs
                        team1_total_wickets = (float(team1_wicket)/team1_proper_overs) * 20
                    else:
                        team1_rr = team1_run/float(team1_over)
                        team1_total_wickets = (float(team1_wicket)/float(team1_overs)) * 20

                    team1_total_balls = float(team1_over) * 6 + float(team1_ball)
                    team1_runs_per_ball = float(team1_run) / team1_total_balls
                    team1_total_runs = float(team1_runs_per_ball * 120)

                team2_run, team2_wicket = team2_score.split("-")
                team2_run = float(team2_run)
                if "." in team2_overs:
                    team2_over, team2_ball = team2_overs.split(".")
                    if team2_ball != 0:
                        team2_proper_overs = float(team2_over) + (float(team2_ball)/6)
                        team2_rr = team2_run/team2_proper_overs
                        team2_total_wickets = (float(team2_wicket)/team2_proper_overs) * 20
                    else:
                        team2_rr = team2_run/float(team2_over)
                        team2_total_wickets = (float(team2_wicket)/float(team2_overs)) * 20

                    team2_total_balls = float(team2_over) * 6 + float(team2_ball)
                    team2_runs_per_ball = float(team2_run) / team2_total_balls
                    team2_total_runs = float(team2_runs_per_ball * 120)

                print("Team 1 Overs: ", team1_overs)
                print("Team 1 Total Runs: ", team1_total_runs)
                print("Team 1 Total Wickets: ", team1_total_wickets)
                print(f"Match {i + 1}: {team1_name_score} scored {team1_score}\n")

                print("Team 2 Overs: ", team2_overs)
                print("Team 2 Total Runs: ", team2_total_runs)
                print("Team 2 Total Wickets: ", team2_total_wickets)
                print(f"Match {i + 1}: {team2_name_score} scored {team2_score}\n")

                nrr = team1_rr - team2_rr
                print("TEAM 1: ", team1_rr)
                print("TEAM 2: ", team2_rr)
                print("NRR: ", nrr)
                print("\n")

                if team1_total_wickets > 10:
                    team1_total_wickets = 10

                if team2_total_wickets > 10:
                    team2_total_wickets = 10

                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total Wickets"] = int(team1_total_wickets)
                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total Runs"] = int(team1_total_runs)
                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total RR"] = int(team1_rr)
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total Wickets"] = int(team2_total_wickets)
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total Runs"] = int(team2_total_runs)
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total RR"] = int(team2_rr)
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total Wickets"] = team2_wicket
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total Runs"] = team2_total_runs
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total NRR"] = team2_rr

                all_nrr[f"Match {i + 1}"] = nrr

            elif team2_short_name_score == team_short_name:
                team1_score_index = team_script.find("score2:") + 7
                team1_score_last_index = team_script[team1_score_index:].find(",")
                team1_score = team_script[team1_score_index:team1_score_index + team1_score_last_index]

                team1_overs_index = team_script.find("over2:") + 6
                team1_overs_last_index = team_script[team1_overs_index:].find(",")
                team1_overs = team_script[team1_overs_index:team1_overs_index + team1_overs_last_index].replace(")","").replace("(","")

                team2_score_index = team_script.find("score1:") + 7
                team2_score_last_index = team_script[team2_score_index:].find(",")
                team2_score = team_script[team2_score_index:team2_score_index + team2_score_last_index]

                team2_overs_index = team_script.find("over1:") + 6
                team2_overs_last_index = team_script[team2_overs_index:].find(",")
                team2_overs = team_script[team2_overs_index:team2_overs_index + team2_overs_last_index].replace(")","").replace("(","")

                team2_run, team2_wicket = team2_score.split("-")
                team2_run = float(team2_run)
                if "." in team2_overs:
                    team2_over, team2_ball = team2_overs.split(".")
                    if team2_ball != 0:
                        team2_proper_overs = float(team2_over) + (float(team2_ball)/6)
                        team2_rr = team2_run/team2_proper_overs
                        team2_total_wickets = (float(team2_wicket)/team2_proper_overs) * 20
                    else:
                        team2_rr = team2_run/float(team2_over)
                        team2_total_wickets = (float(team2_wicket)/float(team2_overs)) * 20

                    team2_total_balls = float(team2_over) * 6 + float(team2_ball)
                    team2_runs_per_ball = float(team2_run) / team2_total_balls
                    team2_total_runs = float(team2_runs_per_ball * 120)
                    
                team1_run, team1_wicket = team1_score.split("-")
                team1_run = float(team1_run)
                if "." in team1_overs:
                    team1_over, team1_ball = team1_overs.split(".")
                    if team1_ball != 0:
                        team1_proper_overs = float(team1_over) + (float(team1_ball)/6)
                        team1_rr = team1_run/team1_proper_overs
                        team1_total_wickets = (float(team1_wicket)/team1_proper_overs) * 20
                    else:
                        team1_rr = team1_run/float(team1_over)
                        team1_total_wickets = (float(team1_wicket)/float(team1_overs)) * 20

                    team1_total_balls = float(team1_over) * 6 + float(team1_ball)
                    team1_runs_per_ball = float(team1_run) / team1_total_balls
                    team1_total_runs = float(team1_runs_per_ball * 120)

                print("Team 2 Overs: ", team1_overs)
                print("Team 2 Total Runs: ", team1_total_runs)
                print("Team 2 Total Wickets: ", team1_total_wickets)
                print(f"Match {i + 1}: {team2_name_score} scored {team1_score}\n")

                print("Team 1 Overs: ", team2_overs)
                print("Team 1 Total Runs: ", team2_total_runs)
                print("Team 1 Total Wickets: ", team2_total_wickets)
                print(f"Match {i + 1}: {team1_name_score} scored {team2_score}\n")

                nrr = team1_rr - team2_rr
                print("TEAM 1: ", team1_rr)
                print("TEAM 2: ", team2_rr)
                print("NRR: ", nrr)
                print("\n")

                if team1_total_wickets > 10:
                    team1_total_wickets = 10

                if team2_total_wickets > 10:
                    team2_total_wickets = 10
                    
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total Wickets"] = int(team1_total_wickets)
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total Runs"] = int(team1_total_runs)
                all_teams_wickets_runs[f"Match {i + 1}"][team2_short_name_score]["Total RR"] = int(team1_rr)
                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total Wickets"] = int(team2_total_wickets)
                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total Runs"] = int(team2_total_runs)
                all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name_score]["Total RR"] = int(team2_rr)
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total Wickets"] = team1_wicket
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total Runs"] = team1_total_runs
                # all_teams_wickets_runs[f"Match {i + 1}"][team1_short_name]["Total NRR"] = team1_rr

                all_nrr[f"Match {i + 1}"] = nrr


            # print(f"Match {i + 1}: {team1_short_name_score} vs {team2_short_name_score}")
            # elif team2_short_name_score == team1_short_name:
            #     team1_overs_index = team1_script.find("over2:") + 6
            #     team1_overs_last_index = team1_script[team1_overs_index:].find(",")
            #     team1_overs = team1_script[team1_overs_index:team1_overs_index + team1_overs_last_index].replace(")","").replace("(","")

            #     team2_score_index = team1_script.find("score2:") + 7
            #     team2_score_last_index = team1_script[team2_score_index:].find(",")
            #     team2_score = team1_script[team2_score_index:team2_score_index + team2_score_last_index]

            #     run, wicket = team2_score.split("-")
            #     if "." in team1_overs:
            #         over, ball = team1_overs.split(".")
            #         total_balls = int(over) * 6 + int(ball)
            #         runs_per_ball = int(run) / total_balls
            #         total_runs = int(runs_per_ball * 120)
                    
            #     print("Overs: ", team1_overs)
            #     print("Total Runs: ", total_runs)
            #     print("Wickets: ", wicket)
            #     print(f"Match {i + 1}: {team1_short_name} scored {team2_score}")

            # elif team2_short_name_score == team2_short_name:
            #     team1_overs_index = team1_script.find("over2:") + 6
            #     team1_overs_last_index = team1_script[team1_overs_index:].find(",")
            #     team1_overs = team1_script[team1_overs_index:team1_overs_index + team1_overs_last_index].replace(")","").replace("(","")

            #     team2_score_index = team1_script.find("score2:") + 7
            #     team2_score_last_index = team1_script[team2_score_index:].find(",")
            #     team2_score = team1_script[team2_score_index:team2_score_index + team2_score_last_index]

            #     run, wicket = team2_score.split("-")
            #     if "." in team1_overs:
            #         over, ball = team1_overs.split(".")
            #         total_balls = int(over) * 6 + int(ball)
            #         runs_per_ball = int(run) / total_balls
            #         total_runs = int(runs_per_ball * 120)

            #     print("Runs: ", run)
            #     print("Overs: ", team1_overs)
            #     print("Total Runs: ", total_runs)
            #     print("Wickets: ", wicket)
            #     print(f"Match {i + 1}: {team2_short_name} scored {team2_score}")

            print(50 * "-")
            

            i += 1

        print("\n")
        print(all_teams_wickets_runs)
        print("\n")
        print(all_nrr)
        print("\n")

        return all_teams_wickets_runs, all_nrr


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
