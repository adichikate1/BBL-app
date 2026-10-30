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
