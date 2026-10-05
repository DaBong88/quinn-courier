# Courier setup (about 30 minutes, desktop browser easiest)

## A. GitHub (5 min)
1. github.com > New repository > name: quinn-courier > Public (Instagram needs public image links) > Create.
2. Upload everything in this folder (drag the unzipped files into "uploading an existing file"). Keep the .github folder.
3. Settings > Actions > General > Workflow permissions > Read and write.
4. Leave control.json as {"paused": true} for now.

## B. X (Quinn's account) (10 min)
1. Create the QuinnCraftAI X account if it does not exist. Mark it as automated, and note it is an AI in the bio.
2. developer.x.com > create a project and app > User authentication settings > App permissions: Read and write.
3. Keys and tokens tab: generate API Key, API Key Secret, Access Token, Access Token Secret. Check the Access Token says "Read and Write".
4. Add credits (pay per use, about $0.015 per post without a link).

## C. Instagram (10 min)
1. QuinnCraftAI must be an Instagram professional account (Creator or Business).
2. developers.facebook.com > Create app > add the Instagram product (Instagram API with Instagram login).
3. Add QuinnCraftAI as a tester, accept the invite in Instagram.
4. Generate a long-lived access token with instagram_business_basic and instagram_business_content_publish. Note the Instagram user ID.
5. Long-lived tokens last 60 days. Put a reminder in your calendar to refresh.

## D. Secrets
GitHub repo > Settings > Secrets and variables > Actions > New secret, one each:
IG_USER_ID, IG_ACCESS_TOKEN, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
Never paste these into chat.

## E. Dry run
Actions tab > Courier publish > Run workflow > dry_run = true. It should finish green and post nothing.

## F. Go live
Tell Quinn the repo name. She connects the bridge (dashboard approvals to queue/jobs.json), then you set control.json paused to false.
