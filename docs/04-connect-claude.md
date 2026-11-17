# 04. Add the redirect URI and connect Claude

## Steps

### 1. Add the redirect URI to the OAuth client

Back in **Google Auth Platform**, **Clients**, open the client from step 02. Under **Authorized redirect URIs**, click **Add URI**, paste the `/auth/callback` URL printed by the deploy script and click **Save**.

```
https://<service>-<project-number>.<region>.run.app/auth/callback
```

Google says changes can take a few minutes to apply.

### 2. Test it on your own account first

In Claude, go to **Settings**, **Connectors**, **Add custom connector**:

- **Name:** Search Console
- **URL:** `https://<service>-<project-number>.<region>.run.app/mcp`
- Leave the advanced OAuth fields empty.

Click **Connect**. A Google sign in opens. Choose your Workspace account and allow access.

Then, in a new chat, ask:

> list my Search Console sites

### 3. Roll it out to the team

When it works for you, an organization owner adds the same URL under **Admin settings**, **Connectors**, so everyone sees it. Each person clicks Connect and signs in with their own Google account.

Check with a second account that each person only sees their own properties.

## Things to try

- "show page 2 opportunities for sc-domain:example.com"
- "which pages have a low CTR for their ranking?"
- "what lost the most clicks in the last 28 days vs the 28 before?"
- "inspect https://www.example.com/some-page/"

Search Console data lags about 2 to 3 days, so date ranges end 3 days ago by default.

## If Connect fails

- `invalid_client: The provided client secret is invalid`: see [05. Client secret fix](05-client-secret-fix.md).
- `Internal Server Error`: see [06. Internal Server Error fix](06-internal-server-error-fix.md).
- `redirect_uri_mismatch`: the redirect URI in step 1 is missing or has a typo.
