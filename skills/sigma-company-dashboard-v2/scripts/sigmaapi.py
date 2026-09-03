"""Sigma API helper, retargeted from Connor's papercranestaging laptop setup to
this session's real org: **papercrane on production** (api.sigmacomputing.com).

Everything below was originally hardcoded to papercranestaging -- BASE, the
client-credential source, the connection id and the target folder are all
per-environment, not per-company, so they're fixed here rather than in
company.py. Reads SIGMA_BASE_URL / SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET from
the process environment (already provisioned in this session) and caches the
bearer token in /tmp/.tok_papercrane (55-minute TTL, same convention as the
other toolkits).

Verified 2026-09-03 against papercrane (production):
  * Workbook spec bodies wrap everything except `name`/`folderId` in `document`.
  * Report spec bodies do the same, with `document.kind: report`.
"""

import base64
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_CACHE = pathlib.Path("/tmp/.tok_papercrane")
TOKEN_TTL = 55 * 60

BASE = os.environ.get("SIGMA_BASE_URL", "https://api.sigmacomputing.com")

# Michelle Koppel's homeFolderId on papercrane (GET /v2/members, this session,
# 2026-09-03) -- "put it in my documents folder" resolves here, not to a
# shared Claude-builder scratch folder.
FOLDER_CLAUDE_BUILDER = "004d8497-18ea-4cf6-a8c5-deca403c22d9"

# "Sigma Sample Database" on papercrane. Originally used DEMO_ACTUARY
# (thematically apt, and /v2/connections/{id}/test reported read/write
# SUCCESS) but that connection's Snowflake account has no SNOWFLAKE.CORTEX
# access -- the AI-insight band's CallText("SNOWFLAKE.CORTEX.COMPLETE", ...)
# fails at query time (not at create; verify/create don't execute SQL, only
# resolve it). Confirmed by probing four Snowflake connections directly with
# a throwaway one-element workbook: DEMO_ACTUARY and DEMO_STAGING both fail
# Cortex calls, "Sigma Sample Database" and CXA_CORE both succeed (including
# with the exact model name "claude-4-sonnet" this build uses), 2026-09-03.
CONN_SNOWFLAKE = "bee6615c-7d11-435c-8819-e32207b27fe4"


class SigmaError(RuntimeError):
    """An API call returned a non-2xx status. `body` holds the decoded payload."""

    def __init__(self, status, body, url):
        self.status = status
        self.body = body
        self.url = url
        super().__init__("HTTP %s on %s\n%s" % (status, url, body))


def _fetch_token():
    cid = os.environ["SIGMA_CLIENT_ID"]
    csec = os.environ["SIGMA_CLIENT_SECRET"]
    cred = base64.b64encode(("%s:%s" % (cid, csec)).encode()).decode()
    req = urllib.request.Request(
        BASE + "/v2/auth/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": "Basic " + cred,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        tok = json.load(resp)["access_token"]
    TOKEN_CACHE.write_text(tok)
    os.chmod(TOKEN_CACHE, 0o600)
    return tok


def token():
    """Cached bearer token, refreshed once the cache file ages past the TTL."""
    if TOKEN_CACHE.exists() and time.time() - TOKEN_CACHE.stat().st_mtime < TOKEN_TTL:
        cached = TOKEN_CACHE.read_text().strip()
        if cached:
            return cached
    return _fetch_token()


def call(method, path, body=None, accept="application/json", retry_auth=True):
    """Issue an API call. Returns parsed JSON, or raw text when not JSON."""
    url = BASE + path
    data = None
    headers = {"Authorization": "Bearer " + token(), "Accept": accept}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        # A cached token can expire mid-build; refresh once and replay.
        if exc.code == 401 and retry_auth:
            _fetch_token()
            return call(method, path, body, accept, retry_auth=False)
        try:
            raw = json.dumps(json.loads(raw), indent=2)
        except ValueError:
            pass
        raise SigmaError(exc.code, raw, url) from None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


# ---------------------------------------------------------------- workbooks


def verify_workbook(spec):
    return call("POST", "/v2/workbooks/spec/verify", spec)


def create_workbook(spec):
    return call("POST", "/v2/workbooks/spec", spec)


def update_workbook(workbook_id, spec):
    return call("PUT", "/v2/workbooks/%s/spec" % workbook_id, spec)


def get_workbook(workbook_id):
    return call("GET", "/v2/workbooks/%s/spec" % workbook_id)


def get_workbook_meta(workbook_id):
    # Cheap: no spec body, just latestVersion/updatedAt/updatedBy. Use this to
    # check whether someone edited the workbook since we last pushed, without
    # paying for a full spec fetch every time.
    return call("GET", "/v2/workbooks/%s" % workbook_id)


# ------------------------------------------------------------------ reports


def create_report(spec):
    return call("POST", "/v2/reports/spec", spec)


def update_report(report_id, spec):
    return call("PUT", "/v2/reports/%s/spec" % report_id, spec)


def get_report(report_id):
    return call("GET", "/v2/reports/%s/spec" % report_id)


# ------------------------------------------------------------------ plugins


def register_plugin(name, url, description=""):
    return call(
        "POST",
        "/v2/plugins",
        {"name": name, "url": url, "description": description, "type": "element"},
    )


def list_plugins():
    return call("GET", "/v2/plugins")


def describe(obj, limit=4000):
    """Pretty-print helper for poking at responses from the shell."""
    text = json.dumps(obj, indent=2) if not isinstance(obj, str) else obj
    return text[:limit]


if __name__ == "__main__":
    print("token ok, len", len(token()))
    print(describe(call("GET", "/v2/whoami")))
