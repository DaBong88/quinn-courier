# Courier (publisher)
Posts approved jobs to Quinn's Instagram and X from GitHub Actions. Stdlib Python only.

Setup (when real accounts exist)
1. Create a public GitHub repo, upload this folder.
2. Settings > Secrets > Actions: IG_USER_ID, IG_ACCESS_TOKEN, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET.
3. Keep control.json {"paused": true} until you are ready; run the workflow with dry_run=true first.
4. queue/jobs.json is filled by the bridge (a scheduled Claude task) from approved dashboard jobs. Jobs carry approvedHash = sha256(caption|mediaId|account|scheduledFor); any edit voids it.
5. Instagram needs a public image URL (use unguessable file names in the repo).
Test: python3 tests/test_publish.py
