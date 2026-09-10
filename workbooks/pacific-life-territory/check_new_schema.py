#!/usr/bin/env python3
"""Ad-hoc sanity checks for the NEW (2026-08) document{} schema, since
scripts/validate-spec.py still targets the old pages[].elements shape.
"""
import json, re, sys
import xml.etree.ElementTree as ET

spec = json.load(open(sys.argv[1]))
doc = spec["document"]
layout = doc["layout"]
elements = doc["elements"]

issues = []

# duplicate element ids
ids = [e["id"] for e in elements]
dupes = {i for i in ids if ids.count(i) > 1}
if dupes:
    issues.append(f"duplicate element ids: {dupes}")

# parse layout (multiple <Page> siblings)
cleaned = re.sub(r"<\?xml[^?]*\?>", "", layout).strip()
root = ET.fromstring(f"<root>{cleaned}</root>")

placed = {el.get("elementId") for el in root.iter() if el.tag in ("Element", "Container")}
for eid in ids:
    if eid not in placed:
        issues.append(f"element `{eid}` not placed in layout (Element/Container elementId)")

# containers have children
container_ids = [e["id"] for e in elements if e.get("kind") == "container"]
for cid in container_ids:
    node = next((el for el in root.iter("Container") if el.get("elementId") == cid), None)
    if node is None:
        issues.append(f"container `{cid}`: no matching <Container> in layout")
    elif len(list(node)) == 0:
        issues.append(f"container `{cid}`: <Container> has no nested children")

# page ids referenced in layout match declared pages
page_ids_layout = {el.get("id") for el in root.findall("Page")}
page_ids_spec = {p["id"] for p in doc["pages"]}
if page_ids_layout != page_ids_spec:
    issues.append(f"page id mismatch: layout={page_ids_layout} spec={page_ids_spec}")

# controlId uniqueness
seen = {}
for e in elements:
    if e.get("kind") == "control":
        cid = e.get("controlId")
        if cid in seen:
            issues.append(f"duplicate controlId `{cid}` on {seen[cid]} and {e['id']}")
        else:
            seen[cid] = e["id"]

# column format shape sanity (must have 'kind' if present)
for e in elements:
    for c in e.get("columns", []) or []:
        fmt = c.get("format")
        if fmt is not None and "kind" not in fmt:
            issues.append(f"element `{e['id']}` column `{c.get('id')}` format missing 'kind'")

if issues:
    print(f"{len(issues)} issue(s):")
    for i in issues:
        print(" -", i)
    sys.exit(1)
else:
    print(f"OK — {len(elements)} elements, {len(doc['pages'])} pages, all placed, no dupes.")
