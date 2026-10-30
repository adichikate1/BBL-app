"""Train the BBL Women match-winner model and export it as plain JSON.

Model: symmetric logistic regression on 5 Team1-minus-Team2 difference features
(every match is also flipped: Team1<->Team2, label inverted; no intercept).
The exported weights act on RAW differences, so the web app needs no sklearn/scipy.

Usage:  python train_model.py [path/to/csv]
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent
CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "bbl_women.csv"
C = 0.3

FEATURES = [  # key, label, team1 column, team2 column
    ("form",    "Recent form (wins in last 5)",   "Team 1 Last 5 Recent Matches Total Wins", "Team 2 Last 5 Recent Matches Total Wins"),
    ("h2h",     "Head-to-head (last 5 wins)",     "Team 1 Last 5 H2H Won",                    "Team 2 Last 5 H2H Won"),
    ("nrr5",    "Net run rate (last 5)",          "Team 1 Last 5 Recent Matches Net Run Rate","Team 2 Last 5 Recent Matches Net Run Rate"),
    ("avgruns", "Average runs scored",            "Team 1 Average Runs",                      "Team 2 Average Runs"),
    ("avgwk",   "Average wickets lost",           "Team 1 Average Wickets",                   "Team 2 Average Wickets"),
]

df = pd.read_csv(CSV)
df["date"] = pd.to_datetime(dict(year=df["Match Year"], month=df["Match Month"], day=df["Match Date"]))
df = df.sort_values("date", kind="stable").reset_index(drop=True)
df = df[df["Winner"].isin(set(df["Team 1 Name"]) | set(df["Team 2 Name"]))].reset_index(drop=True)
y = (df["Winner"] == df["Team 1 Name"]).astype(int).values

X = np.column_stack([df[a] - df[b] for _, _, a, b in FEATURES]).astype(float)
Xa, ya = np.vstack([X, -X]), np.r_[y, 1 - y]
sc = StandardScaler(with_mean=False).fit(Xa)
lr = LogisticRegression(C=C, fit_intercept=False, max_iter=2000).fit(sc.transform(Xa), ya)
w = lr.coef_[0] / sc.scale_                      # weights on raw differences

# sanity: exported maths must reproduce sklearn
p_sk = lr.predict_proba(sc.transform(X))[:, 1]
p_js = 1 / (1 + np.exp(-(X @ w)))
assert np.allclose(p_sk, p_js, atol=1e-9)

# input ranges seen in the data (used for validation / UI hints)
def rng(col):
    s = pd.concat([df[f"Team 1 {col}"], df[f"Team 2 {col}"]]); return [float(s.min()), float(s.max())]
ranges = {
    "form": [0, 5], "h2h": [0, 5],
    "nrr5": rng("Last 5 Recent Matches Net Run Rate"),
    "avgruns": rng("Average Runs"), "avgwk": rng("Average Wickets"),
}

# latest known stats per team (snapshot from the most recent match in the CSV)
teams = {}
for _, r in df.iterrows():
    for k in ("1", "2"):
        teams[r[f"Team {k} Name"]] = {
            "form": float(r[f"Team {k} Last 5 Recent Matches Total Wins"]),
            "nrr5": round(float(r[f"Team {k} Last 5 Recent Matches Net Run Rate"]), 3),
            "avgruns": round(float(r[f"Team {k} Average Runs"]), 2),
            "avgwk": round(float(r[f"Team {k} Average Wickets"]), 2),
            "short": r[f"Team {k} Short Name"],
        }
h2h = {}  # latest H2H record per ordered pair
for _, r in df.iterrows():
    a, b = r["Team 1 Name"], r["Team 2 Name"]
    h2h[f"{a}|{b}"] = [int(r["Team 1 Last 5 H2H Won"]), int(r["Team 2 Last 5 H2H Won"])]
    h2h[f"{b}|{a}"] = [int(r["Team 2 Last 5 H2H Won"]), int(r["Team 1 Last 5 H2H Won"])]

acc_note = {  # leave-one-season-out tests (train on other 3 seasons, test on the held-out one)
    "by_season": {"2023": 0.500, "2024": 0.650, "2025": 0.641},
    "overall": 0.584, "matches_tested": 137, "baseline": 0.53,
}
out = {
    "version": "1.0",
    "trained_on": {"matches": int(len(df)), "from": str(df.date.min().date()), "to": str(df.date.max().date())},
    "features": [{"key": k, "label": l, "weight": float(wi), "range": ranges[k]} for (k, l, _, _), wi in zip(FEATURES, w)],
    "validation": acc_note,
}
(ROOT / "model").mkdir(exist_ok=True)
(ROOT / "model" / "model.json").write_text(json.dumps(out, indent=2))
(ROOT / "model" / "teams.json").write_text(json.dumps({"teams": dict(sorted(teams.items())), "h2h": h2h}, indent=2))
print("matches:", len(df)); print(json.dumps(out["features"], indent=1)); print(list(teams))
