#!/usr/bin/env python3
"""Bridge step 3: turn queue/results.json into dashboard updates.
Usage: python3 bridge/results.py JOBS_DUMP.json > updates.json
Output: list of {"collection":"jobs","doc_id":..,"if_version":..,"data":{..}} for approved jobs that now have a result.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = json.load(open(os.path.join(ROOT, "queue/results.json")))
docs = json.load(open(sys.argv[1]))
docs = docs if isinstance(docs, list) else docs.get("documents", [])
ups = []
for d in docs:
    r = res.get(d["id"])
    if not r or d["data"].get("stage") != "approved":
        continue
    st, at = r.get("status"), r.get("at")
    if st == "published":
        data = {"stage": "published", "publishedAt": at, "publishedBy": "courier", "publishedUrl": r.get("url"), "error": None}
    elif st in ("failed", "blocked"):
        data = {"stage": st, "error": r.get("detail") or st}
    elif st == "unknown":
        data = {"stage": "failed", "error": "Outcome unknown. Check the platform before retrying. " + (r.get("detail") or "")}
    else:
        continue
    ups.append({"collection": "jobs", "doc_id": d["id"], "if_version": d.get("version"), "data": data})
json.dump(ups, sys.stdout, indent=2)
