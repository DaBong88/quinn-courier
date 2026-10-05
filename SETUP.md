# Courier setup: five handles, each with its own keys

Handles: quinn_x, quinn_ig (Quinn, an AI, labelled) and shaunak_x, shaunak_ig, shaunak_li (yours).
Each handle goes live on its own. Start with one, test it, then add the next.

## A. Repo
Settings > Actions > General > Workflow permissions > Read and write. Keep control.json as {"paused": true}.

## B. X (do once per account: Quinn, then you)
1. developer.x.com: create one project and app. App permissions: Read and write.
2. Use "Authenticate with this app" for each account to generate that account's Access Token and Secret (log in as that account, or generate while logged in as it). Confirm the token says Read and Write.
3. Add credits.
Secrets: <PREFIX>_API_KEY, <PREFIX>_API_SECRET, <PREFIX>_ACCESS_TOKEN, <PREFIX>_ACCESS_SECRET with PREFIX = QUINN_X or SHAUNAK_X. The API key and secret are the same app, so they can be the same values for both.
Quinn's X account: turn on the automated-account label and say AI in the bio.

## C. Instagram (once per account)
1. The account must be a professional account (Creator or Business).
2. developers.facebook.com: create an app, add the Instagram product (Instagram login). Add each account as an Instagram tester and accept the invite in the app.
3. Generate a long-lived token with instagram_business_basic and instagram_business_content_publish, and note the Instagram user ID.
Secrets: <PREFIX>_USER_ID, <PREFIX>_ACCESS_TOKEN with PREFIX = QUINN_IG or SHAUNAK_IG. Tokens last 60 days: put a reminder in your calendar.

## D. LinkedIn (your profile)
1. linkedin.com/developers: create an app and attach a LinkedIn Page (any page you manage). Under Products, add "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect".
2. Generate an access token with scopes w_member_social, openid, profile. Your person ID is the "sub" value from the userinfo call (the token tool shows it).
3. LinkedIn tokens last about 60 days and self-serve apps cannot refresh them silently: re-generate every 2 months. Put a reminder in your calendar.
Secrets: SHAUNAK_LI_ACCESS_TOKEN, SHAUNAK_LI_PERSON_ID.

## E. Dry run
Actions > Courier publish > Run workflow > dry_run = true. Should be green and post nothing.

## F. Go live, one handle at a time
Tell Quinn which handle is ready. She adds it to connectedAccounts on the dashboard. Then unpause in the dashboard.
Never paste keys into chat. They go only into GitHub's secret form.
