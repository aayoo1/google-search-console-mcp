# 06. Internal Server Error when clicking Connect

## Symptom

Clicking Connect in Claude opened a page that just said **Internal Server Error**, before any Google sign in appeared.

## Finding the cause

The Cloud Run logs (Cloud Run, the service, **Logs**) showed the real error:

```
Document name ".../documents/mcp-oauth-proxy-clients/https://claude.ai/oauth/mcp-oauth-client-metadata"
lacks a collection id
```

Claude identifies itself to the server with a client ID that is a **URL** (`https://claude.ai/oauth/...`). The server stores client registrations in Firestore using the client ID as the document ID. Firestore treats `/` as a path separator, so a URL cannot be used as a document ID, and the lookup crashed.

My own test client used a plain ID, so the problem only showed up with Claude's real connection.

## Fix

Tell the Firestore store to encode keys into safe document IDs. In `server/server.py`:

```python
from key_value.aio.stores.firestore import FirestoreStore
from key_value.aio.stores.firestore.store import (
    FirestoreV1CollectionSanitizationStrategy,
    FirestoreV1KeySanitizationStrategy,
)

store = FirestoreStore(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    default_collection="gsc_mcp_oauth",
    key_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
    collection_sanitization_strategy=FirestoreV1CollectionSanitizationStrategy(),
)
```

This is already in the code in this repo. Redeploy with `./deploy.sh` after changing `server.py`.

## Check

Without signing in, this should now return a redirect (302), not a 500:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "https://<service>-<project-number>.<region>.run.app/authorize?response_type=code&client_id=https%3A%2F%2Fclaude.ai%2Foauth%2Fmcp-oauth-client-metadata&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&state=x&scope=openid"
```

## Lesson

If you store OAuth state in Firestore (or any store with restricted key characters), test with Claude's real client ID, not a made up one.
