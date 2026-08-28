#!/usr/bin/env python3
"""PUT an updated spec to the existing live Pacific Life workbook.
Usage: python3 update.py <SIGMA_BASE_URL> <TOKEN> <CONNECTION_ID> <FOLDER_ID> <LOGO_DATAURI_FILE> <WORKBOOK_ID>
"""
import json, sys, urllib.request, urllib.error

WB_ID = sys.argv[6]
sys.argv = sys.argv[:6]
import build

spec = build.build()
with open("spec.json", "w") as f:
    json.dump(spec, f, indent=2)

data = json.dumps(spec).encode()
req = urllib.request.Request(build.BASE + f"/v2/workbooks/{WB_ID}/spec", data=data, headers=build.H, method="PUT")
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("PUT OK", resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print("PUT FAILED", e.read().decode()[:2000])
    sys.exit(1)
