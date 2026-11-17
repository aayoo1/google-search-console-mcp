# 05. Sign in fails with `invalid_client`

## Symptom

Clicking Connect in Claude goes to Google, then lands on an error page:

```
Token exchange with identity provider failed: invalid_client:
The provided client secret is invalid.
```

The server itself was fine. Google was rejecting the client secret stored in Secret Manager.

## What went wrong

It took three tries to find, because the terminal hides what you paste.

1. **The whole JSON file was pasted.** The downloaded client file has several fields. The first saved "secret" was 2,230 characters, the whole file instead of the `GOCSPX-...` value.
2. **The secret was pasted twice.** On the next try the saved value was 70 characters. A real secret is 35. With nothing showing on screen, it is easy to press paste a second time.

A useful check that never shows the secret itself: compare its length.

```bash
S=$(gcloud secrets versions access latest --secret=<oauth-client-secret-name>); echo ${#S}; unset S
```

35 is right. Anything else is wrong.

## Fix

I wrote [`server/set-secret.sh`](../server/set-secret.sh) so this cannot happen again. In Cloud Shell, from the `server/` folder:

```bash
./set-secret.sh                           # paste the GOCSPX-... value when asked
./set-secret.sh client_secret_XXXX.json   # or read it straight from the downloaded JSON
```

It:

- strips stray quotes, commas and spaces picked up when copying from JSON
- spots a double paste and keeps one copy
- refuses anything that is not a valid `GOCSPX-` secret, and saves nothing
- saves a new version in Secret Manager and restarts the Cloud Run service so it picks it up

It prints `Looks valid (35 characters)` and then `Done. Click Connect in Claude again.`

## Clean up

The wrong values are still stored as old secret versions. Once sign in works, destroy them in **Secret Manager**, the secret, **Versions**: select the old versions and **Destroy**. This cannot be undone, so only destroy versions you are sure are wrong. The server always uses the latest version.

## Why a restart is needed

Cloud Run reads secrets when a container starts. Adding a new secret version does nothing until a new revision is deployed. `set-secret.sh` does this by updating an environment variable, which creates a new revision.
