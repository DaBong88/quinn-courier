#!/usr/bin/env python3
"""Courier: publishes approved jobs to Quinn's Instagram and X.

Stdlib only. Reads queue/jobs.json, control.json and state/ledger.json.
Writes state/ledger.json and queue/results.json.
Secrets come from environment variables only (GitHub Actions secrets).

Rules (from courier.md):
  - only stage == "approved" jobs; only allowlisted accounts
  - global pause (control.json "paused": true) stops everything
  - approval is bound to caption|mediaId|account|scheduledFor via approvedHash
  - each job id is published at most once (ledger)
  - never retry a publish call whose outcome is unknown (avoids double posts)
  - bounded retries (3) for clearly transient errors on safe steps
  - DRY_RUN=1 validates everything and calls no API
Exit code 1 if any job failed or is unknown, so GitHub emails one alert.
"""
import base64, hashlib, hmac, json, mimetypes, os, secrets, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOW = {"quinn_ig", "quinn_x"}
LIMITS = {"quinn_ig": 2200, "quinn_x": 280}
IG_BASE = os.environ.get("IG_API_BASE", "https://graph.instagram.com/v25.0")
X_BASE = os.environ.get("X_API_BASE", "https://api.x.com")
DRY = os.environ.get("DRY_RUN") == "1"
POLL_TRIES = int(os.environ.get("IG_POLL_TRIES", "12"))
POLL_SLEEP = float(os.environ.get("IG_POLL_SLEEP", "5"))
RETRY_SLEEP = float(os.environ.get("RETRY_SLEEP", "3"))


class Unknown(Exception):
    """A publish call whose outcome we cannot confirm. Never retried."""


class Fail(Exception):
    pass


def jload(path, default):
    try:
        with open(os.path.join(ROOT, path)) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def jsave(path, data):
    with open(os.path.join(ROOT, path), "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def now():
    return datetime.now(timezone.utc)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def job_hash(j):
    raw = "|".join([j.get("caption") or "", j.get("mediaId") or "", j.get("account") or "", j.get("scheduledFor") or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def env(name):
    v = os.environ.get(name)
    if not v:
        raise Fail("missing secret " + name)
    return v


# ---------- HTTP ----------
def http(method, url, headers=None, body=None, timeout=30):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300].decode("utf-8", "replace")}


def safe_call(fn, tries=3):
    """For idempotent steps only (create container, status, media upload steps)."""
    last = None
    for i in range(tries):
        try:
            status, data = fn()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = "network: %s" % e
        else:
            if status < 400:
                return data
            if status == 429 or status >= 500:
                last = "http %s" % status
            else:
                raise Fail("http %s: %s" % (status, json.dumps(data)[:300]))
        time.sleep(RETRY_SLEEP * (i + 1))
    raise Fail("gave up after %d tries (%s)" % (tries, last))


# ---------- Instagram ----------
def post_instagram(j):
    uid, tok = env("IG_USER_ID"), env("IG_ACCESS_TOKEN")
    if not j.get("mediaUrl"):
        raise Fail("Instagram needs a public mediaUrl")
    form = {"image_url": j["mediaUrl"], "caption": j["caption"], "access_token": tok}
    if j.get("altText"):
        form["alt_text"] = j["altText"]
    hdr = {"Content-Type": "application/x-www-form-urlencoded"}
    data = safe_call(lambda: http("POST", "%s/%s/media" % (IG_BASE, uid), hdr, urllib.parse.urlencode(form).encode()))
    cid = data.get("id")
    if not cid:
        raise Fail("no container id")
    for _ in range(POLL_TRIES):
        st = safe_call(lambda: http("GET", "%s/%s?fields=status_code&access_token=%s" % (IG_BASE, cid, urllib.parse.quote(tok))))
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise Fail("container " + code)
        time.sleep(POLL_SLEEP)
    else:
        raise Fail("container not ready in time")
    # publish call: single attempt only
    body = urllib.parse.urlencode({"creation_id": cid, "access_token": tok}).encode()
    try:
        status, pub = http("POST", "%s/%s/media_publish" % (IG_BASE, uid), hdr, body)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unknown("media_publish outcome unknown: %s" % e)
    if status >= 500 or status == 429:
        raise Unknown("media_publish http %s, check Instagram before retrying" % status)
    if status >= 400:
        raise Fail("media_publish http %s: %s" % (status, json.dumps(pub)[:300]))
    pid = pub.get("id")
    if not pid:
        raise Unknown("media_publish returned no id")
    link = None
    try:
        info = safe_call(lambda: http("GET", "%s/%s?fields=permalink&access_token=%s" % (IG_BASE, pid, urllib.parse.quote(tok))), tries=2)
        link = info.get("permalink")
    except Fail:
        pass
    return {"remoteId": pid, "url": link}


# ---------- X (OAuth 1.0a user context, no token expiry) ----------
def oauth1_header(method, url):
    ck, cs = env("X_API_KEY"), env("X_API_SECRET")
    at, ats = env("X_ACCESS_TOKEN"), env("X_ACCESS_SECRET")
    p = {"oauth_consumer_key": ck, "oauth_nonce": secrets.token_hex(12), "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": at, "oauth_version": "1.0"}
    parts = urllib.parse.urlsplit(url)
    params = dict(urllib.parse.parse_qsl(parts.query))
    params.update(p)
    enc = lambda s: urllib.parse.quote(str(s), safe="~")
    norm = "&".join("%s=%s" % (enc(k), enc(v)) for k, v in sorted(params.items()))
    base_url = "%s://%s%s" % (parts.scheme, parts.netloc, parts.path)
    base = "&".join([method.upper(), enc(base_url), enc(norm)])
    key = "%s&%s" % (enc(cs), enc(ats))
    p["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join('%s="%s"' % (enc(k), enc(v)) for k, v in sorted(p.items()))


def multipart(fields, fname, fbytes, ctype):
    b = "----q" + secrets.token_hex(8)
    out = b""
    for k, v in fields.items():
        out += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode()
    out += ('--%s\r\nContent-Disposition: form-data; name="media"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (b, fname, ctype)).encode()
    out += fbytes + ("\r\n--%s--\r\n" % b).encode()
    return "multipart/form-data; boundary=" + b, out


def x_upload(path):
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        raise Fail("media file missing: " + path)
    data = open(full, "rb").read()
    ctype = mimetypes.guess_type(full)[0] or "image/jpeg"
    u = X_BASE + "/2/media/upload/initialize"
    init = safe_call(lambda: http("POST", u, {"Authorization": oauth1_header("POST", u), "Content-Type": "application/json"},
                                  json.dumps({"total_bytes": len(data), "media_type": ctype, "media_category": "tweet_image"}).encode()))
    mid = (init.get("data") or {}).get("id")
    if not mid:
        raise Fail("no media id from initialize")
    u = "%s/2/media/upload/%s/append" % (X_BASE, mid)
    ct, body = multipart({"segment_index": "0"}, os.path.basename(full), data, ctype)
    safe_call(lambda: http("POST", u, {"Authorization": oauth1_header("POST", u), "Content-Type": ct}, body))
    u = "%s/2/media/upload/%s/finalize" % (X_BASE, mid)
    fin = safe_call(lambda: http("POST", u, {"Authorization": oauth1_header("POST", u)}, b""))
    info = (fin.get("data") or {}).get("processing_info")
    tries = 0
    while info and info.get("state") in ("pending", "in_progress") and tries < 10:
        time.sleep(float(info.get("check_after_secs", 1)))
        u = "%s/2/media/upload?media_id=%s&command=STATUS" % (X_BASE, mid)
        info = (safe_call(lambda: http("GET", u, {"Authorization": oauth1_header("GET", u)})).get("data") or {}).get("processing_info")
        tries += 1
    if info and info.get("state") == "failed":
        raise Fail("X media processing failed")
    return mid


def post_x(j):
    payload = {"text": j["caption"]}
    if j.get("mediaPath"):
        payload["media"] = {"media_ids": [x_upload(j["mediaPath"])]}
    u = X_BASE + "/2/tweets"
    try:
        status, data = http("POST", u, {"Authorization": oauth1_header("POST", u), "Content-Type": "application/json"},
                            json.dumps(payload).encode())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unknown("POST /2/tweets outcome unknown: %s" % e)
    if status >= 500 or status == 429:
        raise Unknown("POST /2/tweets http %s, check X before retrying" % status)
    if status >= 400:
        raise Fail("POST /2/tweets http %s: %s" % (status, json.dumps(data)[:300]))
    tid = (data.get("data") or {}).get("id")
    if not tid:
        raise Unknown("tweet response had no id")
    return {"remoteId": tid, "url": "https://x.com/i/status/" + tid}


# ---------- gatekeeping ----------
def check(j, ledger):
    """Return (ok, reason). reason 'skip' = silently not our business yet."""
    if j.get("stage") != "approved":
        return False, "skip"
    if j["id"] in ledger:
        return False, "skip"
    if j.get("account") not in ALLOW:
        return False, "account not on allowlist: %s" % j.get("account")
    if not j.get("caption", "").strip():
        return False, "empty caption"
    if len(j["caption"]) > LIMITS[j["account"]]:
        return False, "caption too long (%d > %d)" % (len(j["caption"]), LIMITS[j["account"]])
    if not j.get("approvedHash"):
        return False, "no approvedHash"
    if j["approvedHash"] != job_hash(j):
        return False, "approval does not match current content (edited after approval?)"
    if j["account"] == "quinn_ig" and not j.get("mediaUrl"):
        return False, "Instagram post has no media URL"
    if j.get("scheduledFor"):
        try:
            if parse_time(j["scheduledFor"]) > now():
                return False, "skip"
        except ValueError:
            return False, "bad scheduledFor"
    return True, ""


def main():
    control = jload("control.json", {"paused": True})
    if control.get("paused", True):
        print("Paused. Nothing published.")
        return 0
    jobs = jload("queue/jobs.json", [])
    ledger = jload("state/ledger.json", {})
    results = jload("queue/results.json", {})
    bad = 0
    for j in jobs:
        ok, why = check(j, ledger)
        if not ok:
            if why != "skip":
                results[j["id"]] = {"status": "blocked", "detail": why, "at": now().isoformat()}
                print("BLOCKED", j["id"], why)
                bad += 1
            continue
        if DRY:
            results[j["id"]] = {"status": "dry_run_ok", "at": now().isoformat()}
            print("DRY-RUN ok", j["id"], j["account"])
            continue
        try:
            r = post_instagram(j) if j["account"] == "quinn_ig" else post_x(j)
            r.update({"status": "published", "at": now().isoformat()})
            ledger[j["id"]] = r
            results[j["id"]] = r
            print("PUBLISHED", j["id"], r.get("url"))
        except Unknown as e:
            r = {"status": "unknown", "detail": str(e), "at": now().isoformat()}
            ledger[j["id"]] = r  # block any re-attempt until a human checks
            results[j["id"]] = r
            print("UNKNOWN", j["id"], e)
            bad += 1
        except Fail as e:
            results[j["id"]] = {"status": "failed", "detail": str(e), "at": now().isoformat()}
            print("FAILED", j["id"], e)
            bad += 1
        jsave("state/ledger.json", ledger)
        jsave("queue/results.json", results)
    jsave("state/ledger.json", ledger)
    jsave("queue/results.json", results)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
