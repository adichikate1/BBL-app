import pytest
import requests
import app as appmod
import crex_functions as cf
import scraper
from crex_fixture import BH_CODES, build_pages, chunks, make_fake_get

PAGES = build_pages()


@pytest.fixture(autouse=True)
def fake_crex(monkeypatch):
    log = []
    monkeypatch.setattr(cf._requests, "get", make_fake_get(PAGES, log))
    scraper._cache.clear(); appmod._hits.clear()
    return log


def test_full_scrape_values():
    d = scraper.fetch_match("PZ7")
    assert (d["team1_name"], d["team2_name"]) == ("Brisbane Heat Women", "Sydney Sixers Women")
    t1, t2 = d["t1"], d["t2"]
    assert t1["form"] == 3 and t2["form"] == 1                      # W/L/T run-length strings
    assert (t1["h2h"], t2["h2h"]) == (2, 1)                          # a tie counts for nobody
    assert t1["avgruns"] == 150 and t1["avgwk"] == 5 and t1["nrr5"] == pytest.approx(0.5)
    assert t2["avgruns"] == pytest.approx(129.8) and t2["avgwk"] == pytest.approx(5.6)   # int-truncated per match
    assert t2["nrr5"] == pytest.approx((4 * 0.5 + (120 / 18.5 - 119 / 20)) / 5, abs=1e-3)
    assert d["matches_used"] == {"t1": 5, "t2": 5}


def test_every_request_has_timeout_and_targets_crex(fake_crex):
    scraper.fetch_match("PZ7")
    assert len(fake_crex) >= 21                                      # 1 main + 10 validity + 10 scorecards
    assert all(u.startswith("https://crex.com/") and kw.get("timeout") == cf.HTTP_TIMEOUT for u, kw in fake_crex)


def test_cache_avoids_refetch(fake_crex):
    scraper.fetch_match("PZ7"); n = len(fake_crex)
    scraper.fetch_match("PZ7"); assert len(fake_crex) == n


def test_bad_codes():
    for bad in ("", "a", "x" * 9, "PZ 7", "../etc", "PZ7;rm"):
        with pytest.raises(scraper.InvalidCode):
            scraper.fetch_match(bad)
    with pytest.raises(scraper.ScrapeError, match="not found"):
        scraper.fetch_match("NOPE1")


def test_fewer_than_five_past_matches_is_a_clean_error(monkeypatch):
    pages = dict(PAGES); pages["PZ7"] = PAGES["PZ7"].replace(chunks(BH_CODES), chunks(BH_CODES[:3]))
    monkeypatch.setattr(cf._requests, "get", make_fake_get(pages))
    with pytest.raises(scraper.ScrapeError, match="5 earlier matches"):
        scraper.fetch_match("PZ7")


def test_unparseable_past_page_is_a_clean_error(monkeypatch):
    pages = dict(PAGES); pages["AB11"] = "x" * 700 + "garbage"
    monkeypatch.setattr(cf._requests, "get", make_fake_get(pages))
    with pytest.raises(scraper.ScrapeError):
        scraper.fetch_match("PZ7")


def test_missing_past_page_cannot_hang_forever(monkeypatch, fake_crex):
    """get_wicket_lost_and_runs loops while a page is empty; the request budget must break that loop."""
    pages = dict(PAGES); pages.pop("AB10")
    log = []
    monkeypatch.setattr(cf._requests, "get", make_fake_get(pages, log))
    monkeypatch.setattr(cf, "MAX_REQUESTS", 40)
    with pytest.raises(scraper.ScrapeError, match="too slowly"):
        scraper.fetch_match("PZ7")
    assert len(log) <= 41


def test_non_crex_urls_are_blocked():
    with pytest.raises(cf.BudgetExceeded):
        cf.requests.get("http://169.254.169.254/latest/meta-data")


def test_network_error_message(monkeypatch):
    def boom(*a, **k): raise requests.ConnectionError("down")
    monkeypatch.setattr(cf._requests, "get", boom)
    with pytest.raises(scraper.ScrapeError, match="reach CREX"):
        scraper.fetch_match("PZ7")


# ------------------------------------------------------------------ HTTP endpoint
@pytest.fixture
def client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def test_api_fetch_then_predict_roundtrip(client):
    r = client.get("/api/fetch", query_string={"code": "PZ7"})
    assert r.status_code == 200
    j = r.json
    assert j["team1"] == "Brisbane Heat Women" and j["team2"] == "Sydney Sixers Women"
    p = client.post("/api/predict", json={"team1": j["team1"], "team2": j["team2"], "t1": j["t1"], "t2": j["t2"]})
    assert p.status_code == 200 and p.json["winner"] in (j["team1"], j["team2"])


def test_api_fetch_errors(client, monkeypatch):
    assert client.get("/api/fetch", query_string={"code": "bad code!"}).status_code == 422
    assert client.get("/api/fetch").status_code == 422
    assert client.get("/api/fetch", query_string={"code": "NOPE1"}).status_code == 502
    monkeypatch.setattr(scraper, "fetch_match", lambda c: (_ for _ in ()).throw(KeyError("layout")))
    r = client.get("/api/fetch", query_string={"code": "PZ7"})
    assert r.status_code == 502 and "format" in r.json["error"]
    monkeypatch.setattr(scraper, "fetch_match", lambda c: {"code": c, "team1_name": "Delhi Capitals",
        "team2_name": "Sydney Sixers Women", "t1": {}, "t2": {}, "matches_used": {"t1": 5, "t2": 5}})
    r = client.get("/api/fetch", query_string={"code": "PZ7"})
    assert r.status_code == 422 and "not in the model" in r.json["error"]


def test_team_name_mapping():
    assert appmod._model_team("Brisbane Heat") == "Brisbane Heat Women"
    assert appmod._model_team("sydney  sixers women") == "Sydney Sixers Women"
    assert appmod._model_team("Mumbai Indians") is None


def test_fetch_has_its_own_stricter_rate_limit(client, monkeypatch):
    monkeypatch.setattr(appmod, "FETCH_LIMIT", 2)
    codes = [client.get("/api/fetch", query_string={"code": "PZ7"}).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert client.get("/api/teams").status_code == 200       # other endpoints unaffected
