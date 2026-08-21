"""Fix the "Cohort Builder" tab (Tab 2 of the tabbed container on page-exec)
in the live Alliant workbook (69b0edbc-751a-4ea5-840b-d2ceefef824d): the 7
cohort filter controls (Coverage Tier, Age Band, Gender, Relationship, Plan,
Enrollment Tenure, Group Name) already exist in document.elements with
correct `filters` wiring to tbl-cohort-pop -- but they were never PLACED in
the layout XML. Invisible controls can never be set, so tbl-cohort-pop (and
everything sourcing from it -- the "PMPM Cost Distribution / Age Band
Distribution / Top Members by PMPM Cost -- Current Cohort" visuals) always
shows the full unfiltered 2,000-member population. That's the bug the user
is seeing.

Fix is layout-XML only -- zero changes to document.elements. Insert the 7
controls (in a nested 24-col sub-grid, 4 + 3 per row) right after the
existing Cohort Name/Description row, and shift the three elements below
them (the size/PMPM summary stack, the detail table, the saved-cohorts
table) down by 4 rows each to make room, preserving their exact heights.

Usage: python3 fix_cohort_viz_filters.py verify   # dry run, no PUT
       python3 fix_cohort_viz_filters.py apply    # PUT the change
"""
import copy
import sys

import sigmaapi as S

WORKBOOK_ID = "69b0edbc-751a-4ea5-840b-d2ceefef824d"

FILTER_CONTROL_IDS = [
    "ctrl-cohort-tier", "ctrl-cohort-age", "ctrl-cohort-gender",
    "ctrl-cohort-rel",
    "ctrl-cohort-plan", "ctrl-cohort-tenure", "ctrl-cohort-group",
]

OLD_BLOCK = (
    '<Element elementId="9KjlDnkXs4" gridColumn="11 / 13" gridRow="2 / 3"/>\n'
    '      <Element elementId="gyOKl3sneq" type="stack" gridColumn="1 / 13" gridRow="3 / 5"/>\n'
    '      <Element elementId="tbl-cohort-detail" gridColumn="1 / 13" gridRow="5 / 24"/>\n'
    '      <Element elementId="tbl-cohort-saved-view" gridColumn="1 / 13" gridRow="24 / 37"/>'
)

NEW_BLOCK = (
    '<Element elementId="9KjlDnkXs4" gridColumn="11 / 13" gridRow="2 / 3"/>\n'
    '      <Container elementId="ctr-cohort-filters" type="grid" gridColumn="1 / 13" gridRow="3 / 7"'
    ' gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">\n'
    '        <Element elementId="ctrl-cohort-tier" gridColumn="1 / 7" gridRow="1 / 3"/>\n'
    '        <Element elementId="ctrl-cohort-age" gridColumn="7 / 13" gridRow="1 / 3"/>\n'
    '        <Element elementId="ctrl-cohort-gender" gridColumn="13 / 19" gridRow="1 / 3"/>\n'
    '        <Element elementId="ctrl-cohort-rel" gridColumn="19 / 25" gridRow="1 / 3"/>\n'
    '        <Element elementId="ctrl-cohort-plan" gridColumn="1 / 9" gridRow="3 / 5"/>\n'
    '        <Element elementId="ctrl-cohort-tenure" gridColumn="9 / 17" gridRow="3 / 5"/>\n'
    '        <Element elementId="ctrl-cohort-group" gridColumn="17 / 25" gridRow="3 / 5"/>\n'
    '      </Container>\n'
    '      <Element elementId="gyOKl3sneq" type="stack" gridColumn="1 / 13" gridRow="7 / 9"/>\n'
    '      <Element elementId="tbl-cohort-detail" gridColumn="1 / 13" gridRow="9 / 28"/>\n'
    '      <Element elementId="tbl-cohort-saved-view" gridColumn="1 / 13" gridRow="28 / 41"/>'
)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    assert mode in ("verify", "apply")

    spec = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")
    doc = spec["document"]

    if len(doc.get("elements", [])) != 102:
        print(f"REFUSING: element count changed since last verified "
              f"(now {len(doc.get('elements', []))}, expected 102).")
        sys.exit(1)

    existing_ids = {e["id"] for e in doc["elements"]}
    for cid in FILTER_CONTROL_IDS:
        if cid not in existing_ids:
            print(f"REFUSING: control {cid!r} not found in document.elements.")
            sys.exit(1)

    layout = doc["layout"]
    if layout.count(OLD_BLOCK) != 1:
        print(f"REFUSING: anchor block not found exactly once "
              f"(found {layout.count(OLD_BLOCK)} times).")
        sys.exit(1)
    for cid in FILTER_CONTROL_IDS:
        if f'elementId="{cid}"' in layout:
            print(f"REFUSING: {cid!r} is already placed somewhere in the layout.")
            sys.exit(1)

    new_doc = copy.deepcopy(doc)
    new_doc["layout"] = layout.replace(OLD_BLOCK, NEW_BLOCK, 1)
    # elements/agents/pages are untouched -- confirm byte-identical
    assert new_doc["elements"] == doc["elements"]
    assert new_doc.get("agents") == doc.get("agents")
    assert new_doc.get("pages") == doc.get("pages")

    print("Inserting 7 filter controls into the Cohort Builder tab; "
          "shifting 3 elements below them down by 4 rows.")

    if mode == "verify":
        S.call("POST", "/v2/workbooks/spec/verify",
               {"name": spec["name"], "folderId": spec.get("folderId"), "document": new_doc})
        print("verify: OK")
        return

    S.call("PUT", f"/v2/workbooks/{WORKBOOK_ID}/spec", {"document": new_doc})
    print("PUT: OK")

    back = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")["document"]
    if back["elements"] == doc["elements"]:
        print(f"Confirmed: all {len(doc['elements'])} elements byte-identical "
              "after the PUT (this was a layout-only change).")
    else:
        print("WARNING: document.elements changed on GET-back.")
    for cid in FILTER_CONTROL_IDS:
        if f'elementId="{cid}"' in back["layout"]:
            print(f"Confirmed placed: {cid}")
        else:
            print(f"MISSING from layout after PUT: {cid}")


if __name__ == "__main__":
    main()
