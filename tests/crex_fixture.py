"""Synthetic CREX pages in the format the notebook functions parse (served through a fake HTTP layer)."""
import re
import types

PAD = "x" * 700


def match_page(s1, n1, s2, n2, score1, over1, score2, over2):
    return (f"{PAD}team1:{n1},team2:{n2},https:api.goscorer.comapiv3getSV3?id=1,team1:{s1},team2:{s2},"
            f"team1_f_n:{n1},team2_f_n:{n2},score1:{score1},over1:{over1},score2:{score2},over2:{over2},end")


BH, SS = ("BH-W", "Brisbane Heat Women"), ("SS-W", "Sydney Sixers Women")
BH_CODES = [f"AB1{i}" for i in range(5)]
SS_CODES = [f"CD1{i}" for i in range(5)]


def chunks(codes):
    return "|".join(f"Lg-W2{c}" for c in codes)          # result 'W2AB10' -> notebook's result[1]=='2' branch


def build_pages():
    pages = {}
    for i, c in enumerate(BH_CODES):          # BH scores 150-5 (20.0) vs 140-8; alternate home/away
        pages[c] = (match_page(*BH, *SS, "150-5", "(20.0)", "140-8", "(20.0)") if i % 2 == 0 else
                    match_page(*SS, *BH, "140-8", "(20.0)", "150-5", "(20.0)"))
    for i, c in enumerate(SS_CODES):          # SS: four 130-6 vs 120-10, one 120-4 in 18.3 vs 119-9
        if i == 4:
            pages[c] = match_page(*SS, *BH, "120-4", "(18.3)", "119-9", "(20.0)")
        else:
            pages[c] = (match_page(*SS, *BH, "130-6", "(20.0)", "120-10", "(20.0)") if i % 2 else
                        match_page(*BH, *SS, "120-10", "(20.0)", "130-6", "(20.0)"))
    pages["PZ7"] = (f"{PAD}team1:{BH[1]},team2:{SS[1]},t:2025-12-04T08:10:00.000Z,https:api.goscorer.comapiv3getSV3?k=1,team1:{BH[0]},"
                    f"team2:{SS[0]},team1_f_n:{BH[1]},team2_f_n:{SS[1]},tf:W2L1W1L1-L1W1L3,"
                    f"https:api.goscorer.comapiv3getIV4?key=abc,t1f:{chunks(BH_CODES)},t2f:{chunks(SS_CODES)},zz,"
                    "https:stats.crickapi.comlivegetPreLiveStats:{a:[{result:Brisbane Heat Women won by 5 wkts,id:1},"
                    "{result:Sydney Sixers Women won by 3 runs,id:2},{result:Match Tie,id:3},"
                    "{result:Brisbane Heat Women won by 2 wkts,id:4}],more:1}")
    return pages


def html(page):
    return f'<html><body><script id="app-root-state" type="application/json">{page}</script></body></html>'


def make_fake_get(pages, log=None):
    def fake_get(url, **kw):
        if log is not None:
            log.append((url, kw))
        m = re.search(r"match-updates-([^/]+)/match-details", url)
        page = pages.get(m.group(1)) if m else None
        return types.SimpleNamespace(text=html(page) if page else "<html></html>")
    return fake_get
