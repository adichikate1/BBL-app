import logging
import os
import time
from collections import defaultdict, deque

from flask import Flask, jsonify, render_template, request

import github_store
import predictor
import scraper

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # 16 KB is plenty for this API
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bbl")

# --- tiny in-memory rate limiter (per IP, per worker) -----------------------------
RATE_LIMIT, RATE_WINDOW = int(os.getenv("RATE_LIMIT", "60")), 60
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "10"))  # scraping CREX is expensive -> stricter limit
_hits = defaultdict(deque)


def _limited(ip, bucket="api", limit=None):
    limit = RATE_LIMIT if limit is None else limit
    now, q = time.time(), _hits[(bucket, ip)]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or "unknown"


@app.before_request
def rate_limit():
    if not request.path.startswith("/api/"):
        return None
    if request.path.startswith("/api/sync/"):
        request.max_content_length = 1024 * 1024        # a whole ledger is bigger than a prediction
    ip = _client_ip()
    if request.path.startswith("/api/sync/") and _limited(ip, "sync", int(os.getenv("SYNC_LIMIT", "20"))):
        return jsonify(error="Too many sync requests. Please wait a minute."), 429
    if request.path == "/api/fetch" and _limited(ip, "fetch", FETCH_LIMIT):
        return jsonify(error="Too many fetches. Please wait a minute."), 429
    if _limited(ip):
        return jsonify(error="Too many requests. Please wait a minute."), 429


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self'; img-src 'self' data:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# --- pages & API -----------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", model=predictor.MODEL)


@app.get("/tracker")
def tracker():
    return render_template("tracker.html")


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", model_version=predictor.MODEL["version"])


@app.get("/api/teams")
def teams():
    return jsonify(teams=sorted(predictor.TEAMS), features=predictor.FEATURES, validation=predictor.MODEL["validation"])


@app.get("/api/defaults")
def defaults():
    t1, t2 = request.args.get("team1"), request.args.get("team2")
    if t1 not in predictor.TEAMS or t2 not in predictor.TEAMS or t1 == t2:
        return jsonify(error="Select two different valid teams."), 400
    return jsonify(predictor.defaults_for(t1, t2))


def _model_team(name):
    """Map a CREX team name onto one of the model's teams (ignores case/spaces/punctuation)."""
    key = scraper._norm(name)
    for t in predictor.TEAMS:
        if scraper._norm(t) == key:
            return t
    for t in predictor.TEAMS:  # e.g. CREX drops the trailing "Women"
        if scraper._norm(t).startswith(key) and len(key) > 6:
            return t
    return None


@app.get("/api/fetch")
def fetch_from_crex():
    """Look up both teams' stats from a CREX match code so the form can be filled automatically."""
    code = request.args.get("code", "")
    try:
        d = scraper.fetch_match(code)
    except scraper.InvalidCode as e:
        return jsonify(error=str(e)), 422
    except scraper.ScrapeError as e:
        log.warning("fetch %r failed: %s", code, e)
        return jsonify(error=str(e)), 502
    except Exception:  # CREX changed its layout, etc.
        log.exception("fetch %r crashed", code)
        return jsonify(error="Could not read this match from CREX (its page format may have changed)."), 502
    t1, t2 = _model_team(d["team1_name"]), _model_team(d["team2_name"])
    if not t1 or not t2 or t1 == t2:
        return jsonify(error=f"Teams '{d['team1_name']}' vs '{d['team2_name']}' are not in the model "
                             "(it only knows the 8 BBL Women teams)."), 422
    log.info("fetch %s -> %s vs %s", d["code"], t1, t2)
    # the model's pick, so the tracker can fill "my pick" too (best effort: the fetch itself still succeeds)
    try:
        pred = predictor.predict(predictor.validate({"team1": t1, "team2": t2, "t1": d["t1"], "t2": d["t2"]}))
        prediction = {"winner": pred["winner"], "p_team1": pred["p_team1"], "p_team2": pred["p_team2"], "strength": pred["strength"]}
    except predictor.ValidationError:
        prediction = None
    return jsonify(code=d["code"], team1=t1, team2=t2, t1=d["t1"], t2=d["t2"], matches_used=d["matches_used"],
                   date=d["date"], time=d["time"], prediction=prediction,
                   h2h_results=d["h2h_results"], h2h_unmatched=d["h2h_unmatched"])


# --- GitHub sync of the bet ledger -------------------------------------------------
def _sync_guard():
    if not github_store.enabled():
        return jsonify(error="GitHub sync is not configured on the server (set GITHUB_TOKEN, GITHUB_REPO, SYNC_KEY).", enabled=False), 503
    if not github_store.check_key(request.headers.get("X-Sync-Key")):
        return jsonify(error="Wrong sync key."), 401
    return None


@app.get("/api/sync/status")
def sync_status():
    return jsonify(enabled=github_store.enabled())


@app.post("/api/sync/save")
def sync_save():
    if (bad := _sync_guard()):
        return bad
    payload = request.get_json(silent=True)
    try:
        if isinstance(payload, dict) and not payload.get("records") and not payload.get("allow_empty"):
            raise github_store.SyncError("Refusing to overwrite the GitHub ledger with an empty one.", 422)
        res = github_store.save(payload)
    except github_store.SyncError as e:
        log.warning("sync save failed: %s", e)
        return jsonify(error=str(e)), e.status
    log.info("sync save: %s matches, commit %s", res["count"], res["commit"])
    return jsonify(res)


@app.get("/api/sync/load")
def sync_load():
    if (bad := _sync_guard()):
        return bad
    try:
        data = github_store.load()
    except github_store.SyncError as e:
        return jsonify(error=str(e)), e.status
    return jsonify(ledger=data)


@app.post("/api/predict")
def predict():
    payload = request.get_json(silent=True)
    try:
        cleaned = predictor.validate(payload)
    except predictor.ValidationError as e:
        return jsonify(error=str(e)), 422
    result = predictor.predict(cleaned)
    log.info("predict %s vs %s -> %s (%.3f)", result["team1"], result["team2"], result["winner"], result["p_team1"])
    return jsonify(result)


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Not found."), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Request too large."), 413


@app.errorhandler(500)
def server_error(e):
    log.exception("unhandled error: %s", e)
    return jsonify(error="Something went wrong on our side."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")

