#!/usr/bin/env python3
"""Bridge step 1: turn a dump of dashboard jobs into queue/jobs.json for Courier.
Usage: python3 bridge/prepare.py JOBS_DUMP.json MEDIA_DIR
JOBS_DUMP.json: list of {"id":..., "data": {...}, "version": n} (as returned by ArtifactData list)
MEDIA_DIR: files named <mediaId>.<ext> downloaded from the dashboard
Only approved jobs for the five allowlisted accounts that are listed in COURIER_CONNECTED (comma list) whose approvedHash still matches are queued.
Prints one line per skipped job so the bridge can log it.
"""
import hashlib, json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("COURIER_REPO", "DaBong88/quinn-courier")
ALLOW = {"quinn_ig", "quinn_x", "shaunak_ig", "shaunak_x", "shaunak_li"}
CONNECTED = set(filter(None, os.environ.get("COURIER_CONNECTED", ",".join(ALLOW)).split(",")))

def h(j):
    raw = "|".join([j.get("caption") or "", j.get("mediaId") or "", j.get("account") or "", j.get("scheduledFor") or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def find_media(d, mid):
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.split(".")[0] == mid:
            return os.path.join(d, f)

def to_jpeg(src, dst):
    try:
        from PIL import Image
        im = Image.open(src)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.save(dst, "JPEG", quality=92)
        return True
    except Exception:
        with open(src, "rb") as f:
            if f.read(3) == b"\xff\xd8\xff":
                shutil.copy(src, dst)
                return True
    return False

def main(dump, media_dir):
    docs = json.load(open(dump))
    docs = docs if isinstance(docs, list) else docs.get("documents", [])
    out, skipped = [], []
    os.makedirs(os.path.join(ROOT, "media"), exist_ok=True)
    for d in docs:
        j = dict(d["data"]); j["id"] = d["id"]
        if j.get("stage") != "approved" or j.get("account") not in ALLOW:
            continue
        if j["account"] not in CONNECTED:
            skipped.append((j["id"], "account not connected yet: " + j["account"])); continue
        if not j.get("approvedHash") or j["approvedHash"] != h(j):
            skipped.append((j["id"], "approval hash does not match")); continue
        job = {"id": j["id"], "account": j["account"], "stage": "approved", "caption": j["caption"],
               "mediaId": j.get("mediaId") or "", "scheduledFor": j.get("scheduledFor") or "",
               "approvedHash": j["approvedHash"], "altText": (j.get("altText") or "")[:1000]}
        if j.get("mediaId"):
            if j.get("mediaType") == "video":
                skipped.append((j["id"], "video posting is not supported yet")); continue
            src = find_media(media_dir, j["mediaId"])
            if not src:
                skipped.append((j["id"], "media file not downloaded")); continue
            rel = "media/%s.jpg" % j["mediaId"]
            if not to_jpeg(src, os.path.join(ROOT, rel)):
                skipped.append((j["id"], "image could not be converted to JPEG")); continue
            job["mediaPath"] = rel
            job["mediaUrl"] = "https://raw.githubusercontent.com/%s/main/%s" % (REPO, rel)
        elif j["account"].endswith("_ig"):
            skipped.append((j["id"], "Instagram needs an image")); continue
        out.append(job)
    json.dump(out, open(os.path.join(ROOT, "queue/jobs.json"), "w"), indent=2, sort_keys=True)
    print("queued %d, skipped %d" % (len(out), len(skipped)))
    for i, why in skipped:
        print("SKIP", i, why)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
