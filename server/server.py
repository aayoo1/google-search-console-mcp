"""GSC MCP - Google Search Console for Claude.

Each person signs in with their own Google account; every API call uses that
person's token, so they only ever see the Search Console properties they
already have access to. Read-only scope.
"""

import os
from datetime import date, timedelta

from cryptography.fernet import Fernet
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "").lower().lstrip("@")
MAX_ROWS_PER_REQUEST = 25_000  # Search Console API hard limit


def _client_storage():
    """Persist OAuth state in Firestore so restarts don't log people out.

    Falls back to FastMCP's local (ephemeral) store when STORAGE_BACKEND=local,
    which is handy for running on a laptop.
    """
    if os.environ.get("STORAGE_BACKEND", "firestore") == "local":
        return None
    from key_value.aio.stores.firestore import FirestoreStore
    from key_value.aio.stores.firestore.store import (
        FirestoreV1CollectionSanitizationStrategy,
        FirestoreV1KeySanitizationStrategy,
    )
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

    store = FirestoreStore(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        database=os.environ.get("FIRESTORE_DATABASE", "(default)"),
        default_collection="gsc_mcp_oauth",
        # Claude's client ID is a URL ("https://claude.ai/..."); Firestore
        # document IDs can't contain "/", so encode keys before storing.
        key_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
        collection_sanitization_strategy=FirestoreV1CollectionSanitizationStrategy(),
    )
    # Tokens are encrypted before they reach Firestore.
    return FernetEncryptionWrapper(
        key_value=store,
        fernet=Fernet(os.environ["STORAGE_ENCRYPTION_KEY"].encode()),
        raise_on_decryption_error=False,
    )


auth = GoogleProvider(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    base_url=os.environ["BASE_URL"],  # e.g. https://gsc-mcp-xxxx.run.app
    required_scopes=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        GSC_SCOPE,
    ],
    # Stable key so tokens survive restarts and redeploys.
    jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    client_storage=_client_storage(),
)

mcp = FastMCP(
    "GSC MCP",
    auth=auth,
    instructions=(
        "Google Search Console data for the signed-in user. Call list_sites first "
        "to get exact site_url values (e.g. 'sc-domain:example.com' or "
        "'https://www.example.com/'). Search Console data lags about 2-3 days."
    ),
)


# ---------------------------------------------------------------- helpers ---

def _gsc():
    token = get_access_token()
    if token is None:
        raise PermissionError("Not signed in.")
    if ALLOWED_DOMAIN:
        email = (token.claims or {}).get("email") or ""
        if not email.lower().endswith("@" + ALLOWED_DOMAIN):
            raise PermissionError(f"Only @{ALLOWED_DOMAIN} accounts can use this server.")
    creds = Credentials(token.token)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _default_dates(start_date: str | None, end_date: str | None, days: int):
    end = date.fromisoformat(end_date) if end_date else date.today() - timedelta(days=3)
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _query(site_url: str, body: dict, max_rows: int) -> list[dict]:
    """Run a searchanalytics query, paging past the 25k-per-request limit."""
    service = _gsc()
    rows: list[dict] = []
    start_row = 0
    while len(rows) < max_rows:
        page_size = min(MAX_ROWS_PER_REQUEST, max_rows - len(rows))
        req = {**body, "rowLimit": page_size, "startRow": start_row}
        try:
            resp = service.searchanalytics().query(siteUrl=site_url, body=req).execute()
        except HttpError as e:
            raise RuntimeError(f"Search Console API error ({e.status_code}): {e.reason}") from e
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start_row += page_size
    return rows


def _flatten(rows: list[dict], dimensions: list[str]) -> list[dict]:
    out = []
    for r in rows:
        item = dict(zip(dimensions, r.get("keys", [])))
        item.update(
            clicks=r.get("clicks", 0),
            impressions=r.get("impressions", 0),
            ctr=round(r.get("ctr", 0), 4),
            position=round(r.get("position", 0), 1),
        )
        out.append(item)
    return out


def _filters(query_contains: str | None, page_contains: str | None, country: str | None,
             device: str | None) -> list[dict]:
    f = []
    if query_contains:
        f.append({"dimension": "query", "operator": "contains", "expression": query_contains})
    if page_contains:
        f.append({"dimension": "page", "operator": "contains", "expression": page_contains})
    if country:
        f.append({"dimension": "country", "operator": "equals", "expression": country.lower()})
    if device:
        f.append({"dimension": "device", "operator": "equals", "expression": device.upper()})
    return [{"filters": f}] if f else []


# Rough organic CTR by rounded position (desktop+mobile blend). Used only to
# flag pages/queries that under-perform for their rank; tune to your own data.
EXPECTED_CTR = {1: 0.28, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
                6: 0.04, 7: 0.03, 8: 0.025, 9: 0.02, 10: 0.018}


# ------------------------------------------------------------------ tools ---

@mcp.tool
def whoami() -> dict:
    """Show which Google account this connector is signed in as."""
    token = get_access_token()
    return {"email": (token.claims or {}).get("email") if token else None}


@mcp.tool
def list_sites() -> list[dict]:
    """List the Search Console properties the signed-in user can access."""
    resp = _gsc().sites().list().execute()
    return resp.get("siteEntry", [])


@mcp.tool
def search_analytics(
    site_url: str,
    start_date: str | None = None,
    end_date: str | None = None,
    dimensions: list[str] | None = None,
    query_contains: str | None = None,
    page_contains: str | None = None,
    country: str | None = None,
    device: str | None = None,
    search_type: str = "web",
    row_limit: int = 1000,
) -> dict:
    """Query Search Console performance data.

    site_url: exact value from list_sites. Dates are YYYY-MM-DD (default: last 28
    days ending 3 days ago). dimensions: any of query, page, country, device,
    date, searchAppearance (default ["query"]). country is ISO-3166 alpha-3
    (e.g. "gbr"); device is DESKTOP, MOBILE or TABLET. search_type: web, image,
    video, news, discover, googleNews. row_limit up to 100000 (pages automatically).
    """
    dims = dimensions or ["query"]
    start, end = _default_dates(start_date, end_date, 28)
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": dims,
        "type": search_type,
        "dimensionFilterGroups": _filters(query_contains, page_contains, country, device),
    }
    rows = _flatten(_query(site_url, body, min(row_limit, 100_000)), dims)
    return {"site_url": site_url, "start_date": start, "end_date": end,
            "row_count": len(rows), "rows": rows}


@mcp.tool
def page_2_opportunities(
    site_url: str,
    days: int = 28,
    min_impressions: int = 100,
    page_contains: str | None = None,
    limit: int = 50,
) -> dict:
    """Queries ranking on page 2 (avg position 11-20) with real demand.

    These are the cheapest wins: a content refresh or internal links can push
    them onto page 1. Sorted by impressions.
    """
    start, end = _default_dates(None, None, days)
    dims = ["query", "page"]
    body = {"startDate": start, "endDate": end, "dimensions": dims,
            "dimensionFilterGroups": _filters(None, page_contains, None, None)}
    rows = _flatten(_query(site_url, body, 50_000), dims)
    hits = [r for r in rows if 10.5 <= r["position"] <= 20.5 and r["impressions"] >= min_impressions]
    hits.sort(key=lambda r: r["impressions"], reverse=True)
    return {"site_url": site_url, "start_date": start, "end_date": end,
            "count": len(hits), "rows": hits[:limit]}


@mcp.tool
def ctr_opportunities(
    site_url: str,
    days: int = 28,
    min_impressions: int = 200,
    dimension: str = "page",
    limit: int = 50,
) -> dict:
    """Pages (or queries) on page 1 whose CTR is well below normal for their rank.

    Usually a title/meta description problem. 'missed_clicks' estimates the
    extra clicks per period if CTR matched the benchmark for that position.
    dimension: "page" or "query".
    """
    if dimension not in ("page", "query"):
        raise ValueError('dimension must be "page" or "query"')
    start, end = _default_dates(None, None, days)
    body = {"startDate": start, "endDate": end, "dimensions": [dimension]}
    rows = _flatten(_query(site_url, body, 50_000), [dimension])
    hits = []
    for r in rows:
        pos = round(r["position"])
        if r["impressions"] < min_impressions or pos not in EXPECTED_CTR:
            continue
        expected = EXPECTED_CTR[pos]
        if r["ctr"] < expected * 0.6:
            r["expected_ctr"] = expected
            r["missed_clicks"] = round(r["impressions"] * (expected - r["ctr"]))
            hits.append(r)
    hits.sort(key=lambda r: r["missed_clicks"], reverse=True)
    return {"site_url": site_url, "start_date": start, "end_date": end,
            "count": len(hits), "rows": hits[:limit]}


@mcp.tool
def compare_periods(
    site_url: str,
    days: int = 28,
    dimension: str = "page",
    limit: int = 50,
) -> dict:
    """Biggest click gains and losses: last N days vs the N days before.

    dimension: "page" or "query".
    """
    cur_start, cur_end = _default_dates(None, None, days)
    prev_end = (date.fromisoformat(cur_start) - timedelta(days=1)).isoformat()
    prev_start, prev_end = _default_dates(None, prev_end, days)

    def fetch(s, e):
        body = {"startDate": s, "endDate": e, "dimensions": [dimension]}
        return {r[dimension]: r for r in _flatten(_query(site_url, body, 50_000), [dimension])}

    cur, prev = fetch(cur_start, cur_end), fetch(prev_start, prev_end)
    changes = []
    for key in set(cur) | set(prev):
        c, p = cur.get(key, {}), prev.get(key, {})
        changes.append({
            dimension: key,
            "clicks_now": c.get("clicks", 0), "clicks_before": p.get("clicks", 0),
            "click_change": c.get("clicks", 0) - p.get("clicks", 0),
            "position_now": c.get("position"), "position_before": p.get("position"),
        })
    changes.sort(key=lambda r: r["click_change"])
    return {
        "site_url": site_url,
        "current": [cur_start, cur_end], "previous": [prev_start, prev_end],
        "biggest_losses": changes[:limit],
        "biggest_gains": list(reversed(changes[-limit:])),
    }


@mcp.tool
def list_sitemaps(site_url: str) -> list[dict]:
    """List submitted sitemaps with status, errors and warnings."""
    return _gsc().sitemaps().list(siteUrl=site_url).execute().get("sitemap", [])


@mcp.tool
def inspect_url(site_url: str, url: str) -> dict:
    """URL Inspection: index status, canonical, crawl info, mobile usability.

    url must belong to site_url. Limited by Google to ~2,000 calls/day per property.
    """
    body = {"inspectionUrl": url, "siteUrl": site_url}
    resp = _gsc().urlInspection().index().inspect(body=body).execute()
    return resp.get("inspectionResult", resp)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
