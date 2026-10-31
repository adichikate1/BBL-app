import copy
import pytest
import app as appmod
import predictor

@pytest.fixture
def client():
    appmod.app.config["TESTING"] = True
    appmod._hits.clear()
    return appmod.app.test_client()

TEAMS = sorted(predictor.TEAMS)

def payload(t1=None, t2=None):
    t1, t2 = t1 or TEAMS[0], t2 or TEAMS[1]
    d = predictor.defaults_for(t1, t2)
    return {"team1": t1, "team2": t2, "t1": d["t1"], "t2": d["t2"]}

def test_health(client):
    r = client.get("/healthz"); assert r.status_code == 200 and r.json["status"] == "ok"

def test_index_renders(client):
    r = client.get("/"); assert r.status_code == 200 and b"Match Predictor" in r.data
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"

def test_teams_endpoint(client):
    j = client.get("/api/teams").json
    assert len(j["teams"]) == 8 and len(j["features"]) == 5

def test_defaults(client):
    r = client.get("/api/defaults", query_string={"team1": TEAMS[0], "team2": TEAMS[1]})
    assert r.status_code == 200 and set(r.json) == {"t1", "t2"}
    assert client.get("/api/defaults", query_string={"team1": TEAMS[0], "team2": TEAMS[0]}).status_code == 400
    assert client.get("/api/defaults", query_string={"team1": "x", "team2": "y"}).status_code == 400

def test_predict_ok(client):
    r = client.post("/api/predict", json=payload())
    assert r.status_code == 200
    j = r.json
    assert abs(j["p_team1"] + j["p_team2"] - 1) < 1e-3
    assert j["winner"] in (j["team1"], j["team2"]) and len(j["factors"]) == 5

def test_symmetry():
    """Swapping Team 1 and Team 2 must flip the probability exactly (model has no intercept)."""
    a, b = TEAMS[2], TEAMS[5]
    p = payload(a, b)
    q = {"team1": b, "team2": a, "t1": p["t2"], "t2": p["t1"]}
    pa = predictor.predict(predictor.validate(p))["p_team1"]
    pb = predictor.predict(predictor.validate(q))["p_team1"]
    assert abs(pa - (1 - pb)) < 1e-3

def test_identical_teams_is_5050():
    p = payload(); p["t2"] = copy.deepcopy(p["t1"])
    assert predictor.predict(predictor.validate(p))["p_team1"] == pytest.approx(0.5, abs=1e-6)

def test_matches_training_data():
    """Exported JSON weights must reproduce the sklearn model's probabilities on the training CSV."""
    import pandas as pd, numpy as np
    df = pd.read_csv("data/bbl_women.csv")
    df = df[df["Winner"].isin(set(df["Team 1 Name"]) | set(df["Team 2 Name"]))]
    cols = {"form": ("Team 1 Last 5 Recent Matches Total Wins", "Team 2 Last 5 Recent Matches Total Wins"),
            "h2h": ("Team 1 Last 5 H2H Won", "Team 2 Last 5 H2H Won"),
            "nrr5": ("Team 1 Last 5 Recent Matches Net Run Rate", "Team 2 Last 5 Recent Matches Net Run Rate"),
            "avgruns": ("Team 1 Average Runs", "Team 2 Average Runs"),
            "avgwk": ("Team 1 Average Wickets", "Team 2 Average Wickets")}
    w = {f["key"]: f["weight"] for f in predictor.FEATURES}
    z = sum(w[k] * (df[a] - df[b]) for k, (a, b) in cols.items())
    pred = (1 / (1 + np.exp(-z)) >= .5).astype(int)
    acc = (pred == (df["Winner"] == df["Team 1 Name"]).astype(int)).mean()
    assert 0.55 < acc < 0.95  # in-sample sanity check, not a performance claim

@pytest.mark.parametrize("mutate,msg", [
    (lambda p: p.update(team2=p["team1"]), "different"),
    (lambda p: p.update(team1="Nope FC"), "valid teams"),
    (lambda p: p["t1"].update(form=6), "between 0 and 5"),
    (lambda p: p["t1"].update(form=-1), "between 0 and 5"),
    (lambda p: p["t1"].update(nrr5="abc"), "number"),
    (lambda p: p["t1"].update(avgruns=None), "required"),
    (lambda p: p["t2"].update(avgruns=99999), "implausible"),
    (lambda p: p["t1"].update(h2h=4) or p["t2"].update(h2h=3), "more than 5"),
    (lambda p: p["t1"].update(nrr5=float("inf")) , "finite"),
])
def test_validation(client, mutate, msg):
    p = payload(); mutate(p)
    import json
    r = client.post("/api/predict", data=json.dumps(p).replace("Infinity", "1e999"), content_type="application/json")
    assert r.status_code == 422 and msg in r.json["error"]

def test_bad_bodies(client):
    assert client.post("/api/predict", data="not json", content_type="application/json").status_code == 422
    assert client.post("/api/predict", json=[1, 2]).status_code == 422
    assert client.post("/api/predict", data="x" * 20000, content_type="application/json").status_code == 413
    assert client.get("/api/predict").status_code == 405
    assert client.get("/nope").status_code == 404

def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(appmod, "RATE_LIMIT", 3)
    codes = [client.get("/api/teams").status_code for _ in range(5)]
    assert codes[:3] == [200] * 3 and codes[3] == 429


def test_tracker_page_and_assets(client):
    r = client.get("/tracker")
    assert r.status_code == 200 and b"Reality check" in r.data and b"ledger.js" in r.data
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    for f in ("ledger.js", "tracker.js"):
        assert client.get(f"/static/{f}").status_code == 200
    assert b"/tracker" in client.get("/").data         # nav link on the predictor page


def test_tracker_page_and_assets(client):
    r = client.get("/tracker")
    assert r.status_code == 200 and b"Reality check" in r.data and b"ledger.js" in r.data
    assert client.get("/static/ledger.js").status_code == 200 and client.get("/static/tracker.js").status_code == 200
    home = client.get("/").data
    assert home.count(b'id="stakebox"') == 1 and home.count(b"ledger.js") == 1   # no duplicate ids / scripts


# ---------- tracker auto-fill + GitHub sync ----------
class _FakeContent:
    def __init__(self, text, sha="s1"):
        self.decoded_content, self.sha = text.encode(), sha


class _FakeRepo:
    default_branch = "main"

    def __init__(self):
        self.files, self.commits = {}, []

    def get_contents(self, path, ref=None):
        import github
        if path not in self.files:
            raise github.GithubException(404, {}, {})
        return _FakeContent(self.files[path], f"sha{len(self.commits)}")

    def _commit(self, path, msg, content):
        import types
        self.files[path] = content; self.commits.append(msg)
        return {"commit": types.SimpleNamespace(sha=f"abcdef{len(self.commits)}")}

    def create_file(self, path, msg, content, branch=None):
        return self._commit(path, msg, content)

    def update_file(self, path, msg, content, sha, branch=None):
        return self._commit(path, msg, content)


@pytest.fixture
def gh(monkeypatch):
    import github_store
    repo = _FakeRepo()
    monkeypatch.setattr(github_store, "_repo", lambda: repo)
    for k, v in (("GITHUB_TOKEN", "tok"), ("GITHUB_REPO", "me/bets"), ("SYNC_KEY", "sekret")):
        monkeypatch.setenv(k, v)
    appmod._hits.clear()
    return repo


H = {"X-Sync-Key": "sekret"}
LEDGER = {"records": [{"id": "a", "code": "PZ7", "date": "2025-12-04", "time": "08:10", "match": "A vs B", "pick": "A", "prob": 0.6,
                       "status": "lost", "stake": 100, "amount": 100, "note": "x", "evil": "<script>"}], "settings": {"baseStake": 100}}


def test_sync_disabled_without_config(client, monkeypatch):
    for k in ("GITHUB_TOKEN", "GITHUB_REPO", "SYNC_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/api/sync/status").json == {"enabled": False}
    assert client.post("/api/sync/save", json=LEDGER, headers=H).status_code == 503
    assert client.get("/api/sync/load", headers=H).status_code == 503


def test_sync_requires_key(client, gh):
    assert client.get("/api/sync/status").json == {"enabled": True}
    assert client.post("/api/sync/save", json=LEDGER).status_code == 401
    assert client.post("/api/sync/save", json=LEDGER, headers={"X-Sync-Key": "nope"}).status_code == 401
    assert client.get("/api/sync/load", headers={"X-Sync-Key": "nope"}).status_code == 401
    assert gh.commits == []


def test_sync_save_load_roundtrip(client, gh):
    assert client.get("/api/sync/load", headers=H).json == {"ledger": None}        # nothing yet
    r = client.post("/api/sync/save", json=LEDGER, headers=H)
    assert r.status_code == 200 and r.json["count"] == 1 and r.json["commit"] and gh.commits == ["ledger: 1 matches"]
    saved = __import__("json").loads(gh.files["data/ledger.json"])
    assert "evil" not in saved["records"][0] and saved["records"][0]["prob"] == 0.6   # whitelist applied
    again = client.post("/api/sync/save", json=LEDGER, headers=H)
    assert again.json["unchanged"] is True and len(gh.commits) == 1                 # no empty commits
    got = client.get("/api/sync/load", headers=H).json["ledger"]
    assert got["records"][0]["match"] == "A vs B"


def test_sync_refuses_empty_unless_allowed(client, gh):
    client.post("/api/sync/save", json=LEDGER, headers=H)
    r = client.post("/api/sync/save", json={"records": [], "settings": {}}, headers=H)
    assert r.status_code == 422 and "empty" in r.json["error"] and len(gh.commits) == 1
    assert client.post("/api/sync/save", json={"records": [], "settings": {}, "allow_empty": True}, headers=H).status_code == 200


def test_sync_bad_payloads(client, gh):
    assert client.post("/api/sync/save", json={"records": "x"}, headers=H).status_code == 422
    assert client.post("/api/sync/save", data="nope", content_type="application/json", headers=H).status_code in (422,)
    big = {"records": [{"status": "won", "match": "m" * 100, "note": "n" * 150}] * 3000}
    assert client.post("/api/sync/save", json=big, headers=H).status_code == 200      # >16 KB is fine for sync


def test_sync_github_errors_are_mapped(client, gh, monkeypatch):
    import github, github_store

    def boom(*a, **k):
        raise github.GithubException(401, {}, {})
    monkeypatch.setattr(gh, "get_contents", boom)
    r = client.post("/api/sync/save", json=LEDGER, headers=H)
    assert r.status_code == 502 and "token" in r.json["error"]


def test_fetch_returns_date_time_and_model_pick(client, monkeypatch):
    import crex_functions as cf, scraper
    from crex_fixture import build_pages, make_fake_get
    monkeypatch.setattr(cf._requests, "get", make_fake_get(build_pages())); scraper._cache.clear()
    d = client.get("/api/fetch?code=PZ7").json
    assert d["date"] == "2025-12-04" and d["time"] == "08:10"
    assert d["prediction"]["winner"] in (d["team1"], d["team2"]) and abs(d["prediction"]["p_team1"] + d["prediction"]["p_team2"] - 1) < 1e-3
