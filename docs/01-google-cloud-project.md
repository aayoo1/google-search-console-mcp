# 01. Prepare the Google Cloud project

## Why

The server runs on Google Cloud Run and keeps its secrets in Secret Manager and its sign in sessions in Firestore. All of that lives in one Google Cloud project.

## Steps

### 1. Pick a project

Use an existing project or create a new one at https://console.cloud.google.com. I reused the project that already ran my Google Ads MCP, which keeps the team's MCP servers in one place. Note the **project ID** (shown on the project dashboard). It appears as `<project-id>` in the rest of this guide.

You need Owner or Editor on the project.

### 2. Make sure billing is active

Cloud Run, Cloud Build, Firestore and Secret Manager will not enable without a billing account. At team scale this costs very little.

If the project is on a **free trial**, upgrade it to a paid account before relying on the server. When a trial ends, Google stops the project's services, and every MCP server in it goes down.

### 3. Check the OAuth consent screen type

In the console go to **Google Auth Platform**, then **Audience**.

- **Internal** means only accounts in your Google Workspace organization can sign in. This is what I used. It only appears if the project belongs to your Workspace organization.
- **External** works with personal Gmail accounts, but you must add each person as a test user.

If the project already has a consent screen (mine did, from the Ads MCP), there is nothing to change. Internal apps do not need scopes listed on the Data Access page.

### 4. APIs

You do not need to enable anything by hand. `deploy.sh` in step 03 enables Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore and the Search Console API.

Side note: the **Enable** button on the Search Console API page did nothing when I clicked it. The deploy script enabled it without problems.

## Next

[02. Create the OAuth client](02-oauth-client.md)
