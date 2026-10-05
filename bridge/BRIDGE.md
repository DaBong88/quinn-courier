# Courier bridge (run by the "Courier bridge" scheduled task)
Gate: do nothing unless the dashboard document settings/control has publisher == "connected".
1. ArtifactData list jobs (artifact https://claude.ai/artifact/BJcKbCA79An684nQ93AG8m) and save the documents to /tmp/jobs.json.
2. For each approved job (account quinn_ig or quinn_x) with a mediaId, download the asset with the Artifact tool (read, path = mediaId) into /tmp/media (file named <mediaId>.<ext>).
3. Clone the repo, `git pull`, run `python3 bridge/prepare.py /tmp/jobs.json /tmp/media`.
4. Write control.json: {"paused": <settings/control.paused>}. Commit queue/jobs.json, media/ and control.json, push to main.
5. Read queue/results.json, run `python3 bridge/results.py /tmp/jobs.json > /tmp/updates.json` and apply the updates with ArtifactData batch. Add one activity doc.
Never approve, edit captions, change schedules or post by any other route.
