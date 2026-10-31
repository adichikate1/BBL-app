"""Save / load the bet ledger as one JSON file in a GitHub repository (PyGithub).

The token lives only in server environment variables and never reaches the browser:
  GITHUB_TOKEN        fine-grained token with "Contents: read & write" on that one repo
  GITHUB_REPO         "owner/name"
  SYNC_KEY            secret you type once into the Tracker page; without it nobody can write to your repo
  GITHUB_BRANCH       optional (default: the repo's default branch)
  GITHUB_LEDGER_PATH  optional (default: data/ledger.json)
"""
import hmac
import json
import os
import threading

from github import Auth, Github, GithubException

STATUSES = ("pending", "won", "lost", "skipped")
MAX_RECORDS = 5000
_lock = threading.Lock()


class SyncError(Exception):
    """Message is safe to show to the user."""

    def __init__(self, msg, status=502):
        super().__init__(msg)
        self.status = status


def config():
    return {"token": os.getenv("GITHUB_TOKEN", ""), "repo": os.getenv("GITHUB_REPO", ""), "key": os.getenv("SYNC_KEY", ""),
            "branch": os.getenv("GITHUB_BRANCH", ""), "path": os.getenv("GITHUB_LEDGER_PATH", "data/ledger.json")}


def enabled():
    c = config()
    return bool(c["token"] and c["repo"] and c["key"])


def check_key(given):
    return enabled() and hmac.compare_digest(str(given or "").encode(), config()["key"].encode())


def _num(v, d=0.0):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def clean(data):
    """Whitelist + clamp everything that comes from the browser before it is written to the repo."""
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise SyncError("Ledger must be an object with a 'records' list.", 422)
    if len(data["records"]) > MAX_RECORDS:
        raise SyncError("Too many records.", 422)
    recs = []
    for r in data["records"]:
        if not isinstance(r, dict) or r.get("status") not in STATUSES:
            continue
        prob = r.get("prob")
        recs.append({
            "id": str(r.get("id", ""))[:32], "code": str(r.get("code", ""))[:8],
            "date": str(r.get("date", ""))[:10], "time": str(r.get("time", ""))[:5],
            "match": str(r.get("match", ""))[:120], "pick": str(r.get("pick", ""))[:80],
            "prob": round(_num(prob), 4) if prob not in (None, "") and 0 <= _num(prob, -1) <= 1 else None,
            "status": r["status"], "stake": max(0, round(_num(r.get("stake")), 2)),
            "amount": max(0, round(_num(r.get("amount")), 2)), "note": str(r.get("note", ""))[:200],
            "created": int(_num(r.get("created"))),
        })
    s = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    settings = {k: max(0, _num(s.get(k), d)) for k, d in (("baseStake", 100), ("maxStake", 0), ("lossLimit", 0), ("odds", 1.9))}
    return {"version": 1, "records": recs, "settings": settings}


def _repo():  # separate function so tests can replace it
    c = config()
    try:
        return Github(auth=Auth.Token(c["token"]), timeout=15).get_repo(c["repo"])
    except GithubException as e:
        raise _translate(e) from e


def _translate(e):
    st = getattr(e, "status", 0)
    if st in (401, 403):
        return SyncError("GitHub rejected the token (check its permissions: Contents read & write).")
    if st == 404:
        return SyncError("GitHub repo or file not found (check GITHUB_REPO and the token's access to it).")
    return SyncError(f"GitHub error ({st}). Please try again.")


def save(data):
    """Create or update the ledger file. Returns {commit, path, count}."""
    ledger = clean(data)
    c = config()
    body = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    msg = f"ledger: {len(ledger['records'])} matches"
    with _lock:
        repo = _repo()
        branch = c["branch"] or repo.default_branch
        for attempt in (1, 2):               # 2nd attempt only if the file changed under us (409/422)
            try:
                try:
                    cur = repo.get_contents(c["path"], ref=branch)
                except GithubException as e:
                    if e.status != 404:
                        raise
                    res = repo.create_file(c["path"], msg, body, branch=branch)
                else:
                    if cur.decoded_content.decode("utf-8") == body:
                        return {"commit": None, "path": c["path"], "count": len(ledger["records"]), "unchanged": True}
                    res = repo.update_file(c["path"], msg, body, cur.sha, branch=branch)
                return {"commit": res["commit"].sha[:7], "path": c["path"], "count": len(ledger["records"]), "unchanged": False}
            except GithubException as e:
                if attempt == 1 and e.status in (409, 422):
                    continue
                raise _translate(e) from e


def load():
    c = config()
    repo = _repo()
    try:
        f = repo.get_contents(c["path"], ref=c["branch"] or repo.default_branch)
    except GithubException as e:
        if e.status == 404:
            return None                      # nothing saved yet
        raise _translate(e) from e
    try:
        return clean(json.loads(f.decoded_content.decode("utf-8")))
    except (ValueError, SyncError) as e:
        raise SyncError("The ledger file in GitHub is not valid.") from e
