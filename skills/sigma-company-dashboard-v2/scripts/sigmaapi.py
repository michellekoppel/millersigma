"""Sigma production API helper, adapted 2026-08-20 to run against the real
papercrane org (not Connor's papercranestaging) for Michelle Koppel's build.

Reads credentials from /home/user/millersigma/.env (SIGMA_BASE_URL,
SIGMA_CLIENT_ID, SIGMA_CLIENT_SECRET) and caches the bearer token in
/tmp/.tok_papercrane (55-minute TTL, same convention as the other toolkits).

Verified 2026-08-20 against papercrane (org 4ec48fda-3be1-4de8-99a3-84c4b2cf3f4a,
base https://api.sigmacomputing.com):
  * Workbook spec bodies wrap everything except `name`/`folderId` in `document`.
  * Report spec bodies do the same, with `document.kind: report`.
"""

import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ENV_FILE = pathlib.Path("/home/user/millersigma/.env")
TOKEN_CACHE = pathlib.Path("/tmp/.tok_papercrane")
TOKEN_TTL = 55 * 60

BASE = os.environ.get("SIGMA_BASE_URL") or "https://api.sigmacomputing.com"
ORG_ID = "4ec48fda-3be1-4de8-99a3-84c4b2cf3f4a"

# Michelle Koppel's own "My Documents" home folder in papercrane (her
# homeFolderId per GET /v2/members; the API credentials' whoami.userId
# matches her memberId, and GET /v2/files/{id} confirms ownerId + edit
# permission). Confirmed 2026-08-20.
FOLDER_CLAUDE_BUILDER = "004d8497-18ea-4cf6-a8c5-deca403c22d9"

# The generic "Snowflake" connection in papercrane -- resolves SQL at create
# time (confirmed 2026-08-20 via a real `create`, not just `verify`, which
# does not resolve SQL). Supports the Snowflake-dialect generator functions
# (SEQ4, GENERATOR, HASH) every company's SQL relies on.
CONN_SNOWFLAKE = "9e79f38b-a310-405c-aad9-72f762ac6ff1"


class SigmaError(RuntimeError):
    """An API call returned a non-2xx status. `body` holds the decoded payload."""

    def __init__(self, status, body, url):
        self.status = status
        self.body = body
        self.url = url
        super().__init__("HTTP %s on %s\n%s" % (status, url, body))


def _read_env():
    if not ENV_FILE.exists():
        raise SigmaError(0, "missing %s" % ENV_FILE, str(ENV_FILE))
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _fetch_token():
    env = _read_env()
    cid = env["SIGMA_CLIENT_ID"]
    csec = env["SIGMA_CLIENT_SECRET"]
    # Documented flow (help.sigmacomputing.com/reference/generate-client-credentials):
    # grant_type/client_id/client_secret as form fields, no Basic auth header.
    # Verified working directly against papercrane 2026-08-20.
    req = urllib.request.Request(
        BASE + "/v2/auth/token",
        data=urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": csec,
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
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
