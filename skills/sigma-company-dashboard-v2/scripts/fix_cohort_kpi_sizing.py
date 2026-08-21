"""Follow-up fix: the 6 Live/Baseline KPI cards placed into w_zlvlsZ5i by
fix_cohort_viz_filters.py rendered at only 2 grid rows tall -- too short to
show the number, just the label (confirmed via element-level PNG export:
370x36px, title only). Give them a single row at full height (7 units,
matching the ~6-7 units other simple stat KPIs elsewhere in this workbook
use, e.g. kpi-cc-cur-util at 6 units) instead of stacking Live/Baseline in
2 cramped rows. Shifts the 3 charts below down by 2 rows to make room
(footprint grows from 5 to 7 units) and widens ctrl-cohort-pick to match
height for visual alignment.

Usage: python3 fix_cohort_kpi_sizing.py verify   # dry run, no PUT
       python3 fix_cohort_kpi_sizing.py apply    # PUT the change
"""
import copy
import sys

import sigmaapi as S

WORKBOOK_ID = "69b0edbc-751a-4ea5-840b-d2ceefef824d"

OLD_TAB3 = (
    '<Element elementId="ctrl-cohort-pick" gridColumn="1 / 3" gridRow="1 / 6"/>\n'
    '      <Container elementId="w_zlvlsZ5i" type="grid" gridColumn="3 / 13" gridRow="1 / 6"'
    ' gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">\n'
    '        <Element elementId="kpi-cohsize-c" gridColumn="1 / 9" gridRow="1 / 3"/>\n'
    '        <Element elementId="kpi-cohtot-c" gridColumn="9 / 17" gridRow="1 / 3"/>\n'
    '        <Element elementId="kpi-cohavg-c" gridColumn="17 / 25" gridRow="1 / 3"/>\n'
    '        <Element elementId="kpi-cohsize-b" gridColumn="1 / 9" gridRow="3 / 5"/>\n'
    '        <Element elementId="kpi-cohtot-b" gridColumn="9 / 17" gridRow="3 / 5"/>\n'
    '        <Element elementId="kpi-cohavg-b" gridColumn="17 / 25" gridRow="3 / 5"/>\n'
    '      </Container>\n'
    '      <Element elementId="bar-cohort-pmpmdist" gridColumn="1 / 5" gridRow="6 / 18"/>\n'
    '      <Element elementId="bar-cohort-agedist" gridColumn="5 / 8" gridRow="6 / 18"/>\n'
    '      <Element elementId="tbl-cohort-topn" gridColumn="8 / 13" gridRow="6 / 18"/>\n'
    '      <Element elementId="bar-cohort-saved-compare" gridColumn="1 / 13" gridRow="18 / 37"/>'
)

NEW_TAB3 = (
    '<Element elementId="ctrl-cohort-pick" gridColumn="1 / 3" gridRow="1 / 8"/>\n'
    '      <Container elementId="w_zlvlsZ5i" type="grid" gridColumn="3 / 13" gridRow="1 / 8"'
    ' gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">\n'
    '        <Element elementId="kpi-cohsize-c" gridColumn="1 / 5" gridRow="1 / 8"/>\n'
    '        <Element elementId="kpi-cohtot-c" gridColumn="5 / 9" gridRow="1 / 8"/>\n'
    '        <Element elementId="kpi-cohavg-c" gridColumn="9 / 13" gridRow="1 / 8"/>\n'
    '        <Element elementId="kpi-cohsize-b" gridColumn="13 / 17" gridRow="1 / 8"/>\n'
    '        <Element elementId="kpi-cohtot-b" gridColumn="17 / 21" gridRow="1 / 8"/>\n'
    '        <Element elementId="kpi-cohavg-b" gridColumn="21 / 25" gridRow="1 / 8"/>\n'
    '      </Container>\n'
    '      <Element elementId="bar-cohort-pmpmdist" gridColumn="1 / 5" gridRow="8 / 20"/>\n'
    '      <Element elementId="bar-cohort-agedist" gridColumn="5 / 8" gridRow="8 / 20"/>\n'
    '      <Element elementId="tbl-cohort-topn" gridColumn="8 / 13" gridRow="8 / 20"/>\n'
    '      <Element elementId="bar-cohort-saved-compare" gridColumn="1 / 13" gridRow="20 / 39"/>'
)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    assert mode in ("verify", "apply")

    spec = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")
    doc = spec["document"]

    if len(doc.get("elements", [])) != 103:
        print(f"REFUSING: element count changed since last verified "
              f"(now {len(doc.get('elements', []))}, expected 103).")
        sys.exit(1)

    layout = doc["layout"]
    if layout.count(OLD_TAB3) != 1:
        print(f"REFUSING: anchor block not found exactly once "
              f"(found {layout.count(OLD_TAB3)} times).")
        sys.exit(1)

    new_doc = copy.deepcopy(doc)
    new_doc["layout"] = layout.replace(OLD_TAB3, NEW_TAB3, 1)
    assert new_doc["elements"] == doc["elements"]
    assert new_doc.get("agents") == doc.get("agents")
    assert new_doc.get("pages") == doc.get("pages")

    print("Resizing the 6 KPI cards to a single full-height row; shifting "
          "the 3 charts below down by 2 rows.")

    if mode == "verify":
        S.call("POST", "/v2/workbooks/spec/verify",
               {"name": spec["name"], "folderId": spec.get("folderId"), "document": new_doc})
        print("verify: OK")
        return

    S.call("PUT", f"/v2/workbooks/{WORKBOOK_ID}/spec", {"document": new_doc})
    print("PUT: OK")

    back = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")["document"]
    back_by_id = {e["id"]: e for e in back["elements"]}
    mismatches = [e["id"] for e in doc["elements"] if back_by_id.get(e["id"]) != e]
    if not mismatches:
        print(f"Confirmed: all {len(doc['elements'])} elements byte-identical "
              "after the PUT (layout-only change).")
    else:
        print("NOTE: element diff (may be the known benign round-trip "
              "normalization seen on prior PUTs):", mismatches)


if __name__ == "__main__":
    main()
