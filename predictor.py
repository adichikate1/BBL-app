"""Pure-Python inference for the BBL Women match-winner model (no sklearn needed at runtime)."""
import json
import math
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "model"
MODEL = json.loads((MODEL_DIR / "model.json").read_text())
TEAMS_DATA = json.loads((MODEL_DIR / "teams.json").read_text())
TEAMS = TEAMS_DATA["teams"]
H2H = TEAMS_DATA["h2h"]
FEATURES = MODEL["features"]

# per-team inputs the user enters (H2H is entered per team too)
TEAM_FIELDS = ("form", "h2h", "nrr5", "avgruns", "avgwk")


class ValidationError(ValueError):
    pass


def _num(value, name):
    if isinstance(value, bool) or value is None or value == "":
        raise ValidationError(f"{name} is required.")
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number.")
    if not math.isfinite(x):
        raise ValidationError(f"{name} must be a finite number.")
    return x


def validate(payload):
    """Return cleaned dict {team1, team2, t1:{...}, t2:{...}} or raise ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    t1, t2 = payload.get("team1"), payload.get("team2")
    if t1 not in TEAMS or t2 not in TEAMS:
        raise ValidationError("Please select two valid teams.")
    if t1 == t2:
        raise ValidationError("Team 1 and Team 2 must be different.")
    cleaned = {"team1": t1, "team2": t2}
    for side, label in (("t1", t1), ("t2", t2)):
        raw = payload.get(side)
        if not isinstance(raw, dict):
            raise ValidationError(f"Missing stats for {label}.")
        vals = {}
        for f in FEATURES:
            k = f["key"]
            lo, hi = f["range"]
            x = _num(raw.get(k), f"{f['label']} ({label})")
            if k in ("form", "h2h"):
                if not (0 <= x <= 5):
                    raise ValidationError(f"{f['label']} ({label}) must be between 0 and 5.")
            else:
                # generous plausibility window around what the model has seen
                span = hi - lo
                if not (lo - span <= x <= hi + span):
                    raise ValidationError(
                        f"{f['label']} ({label}) looks implausible (expected roughly {lo:.1f} to {hi:.1f})."
                    )
            vals[k] = x
        cleaned[side] = vals
    if cleaned["t1"]["h2h"] + cleaned["t2"]["h2h"] > 5:
        raise ValidationError("Head-to-head wins of both teams cannot add up to more than 5.")
    return cleaned


def predict(cleaned):
    contribs, z = [], 0.0
    for f in FEATURES:
        k = f["key"]
        diff = cleaned["t1"][k] - cleaned["t2"][k]
        c = f["weight"] * diff
        z += c
        contribs.append({"key": k, "label": f["label"], "diff": round(diff, 3), "effect": round(c, 4)})
    p1 = 1.0 / (1.0 + math.exp(-z))
    winner = cleaned["team1"] if p1 >= 0.5 else cleaned["team2"]
    margin = abs(p1 - 0.5)
    strength = "Toss-up" if margin < 0.05 else "Slight edge" if margin < 0.15 else "Clear edge"
    return {
        "team1": cleaned["team1"], "team2": cleaned["team2"],
        "p_team1": round(p1, 4), "p_team2": round(1 - p1, 4),
        "winner": winner, "strength": strength, "factors": contribs,
    }


def defaults_for(team1, team2):
    """Latest known stats for a team pair (used to pre-fill the form)."""
    out = {}
    for side, t, o in (("t1", team1, team2), ("t2", team2, team1)):
        d = dict(TEAMS[t])
        d.pop("short", None)
        rec = H2H.get(f"{t}|{o}")
        d["h2h"] = rec[0] if rec else 0
        out[side] = d
    return out
