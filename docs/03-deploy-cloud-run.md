# 03. Deploy the server to Cloud Run

## Why

Running on Cloud Run gives the team one shared, always on URL. Nobody installs anything locally.

## Before you start

- Steps 01 and 02 done.
- Pick a region close to your team, for example `us-central1` or `europe-west1`. It appears as `<region>` below.

## Steps

### 1. Open Cloud Shell

Go to https://shell.cloud.google.com and select your project. Cloud Shell has `gcloud` installed and signed in already. If it asks to **Authorize Cloud Shell**, click Authorize.

### 2. Get the code into Cloud Shell

Either clone this repo:

```bash
git clone https://github.com/aayoo1/google-search-console-mcp.git
cd google-search-console-mcp/server
```

or upload the `server/` folder with the ⋮ menu, Upload.

### 3. Run the deploy script

```bash
chmod +x deploy.sh set-secret.sh
PROJECT_ID=<project-id> REGION=<region> ALLOWED_DOMAIN=<your-domain> GOOGLE_CLIENT_ID=<client-id> ./deploy.sh
```

`ALLOWED_DOMAIN` is your Workspace domain, for example `example.com`. Only email addresses on that domain can use the server.

What the script does:

1. Enables the APIs listed in step 01.
2. Creates a Firestore database if the project has none. If one already exists (mine did), it is reused, with its own collection.
3. Creates a service account for the server with Firestore access.
4. Asks **once** for the client secret: `Paste the OAuth client secret:`. Paste only the `GOCSPX-...` value, once, then press Enter. Nothing shows on screen while you paste. That is normal.
5. Generates two more keys (JWT signing and token encryption) and stores all three in Secret Manager.
6. Builds and deploys to Cloud Run. The first time, it asks to create an Artifact Registry repo: type `y`.

It finishes in about 3 to 5 minutes and prints two URLs:

```
1. In the OAuth client, add this Authorized redirect URI:
     https://<service>-<project-number>.<region>.run.app/auth/callback
2. Add to Claude as a custom connector with URL:
     https://<service>-<project-number>.<region>.run.app/mcp
```

The URL is predictable (service name, project number, region), so it does not change between deploys.

### 4. Check it is up

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<service>-<project-number>.<region>.run.app/mcp
```

`401` is correct: the server is running and refusing requests that are not signed in.

## Why `--allow-unauthenticated`

Cloud Run's own login check would block Claude from connecting at all. The server's OAuth layer protects `/mcp` instead, so unsigned requests get a 401 and never see data. This is the same pattern as the Ads MCP.

## Settings worth knowing

- `--min-instances 1` keeps one copy warm, so the first request is fast.
- Sign in sessions are in Firestore, so `--max-instances 3` is safe: every copy sees the same sessions.
- Do not rotate the JWT or storage keys in Secret Manager unless you want everyone to reconnect.

## Next

[04. Add the redirect URI and connect Claude](04-connect-claude.md)
