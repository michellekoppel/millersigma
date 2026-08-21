"""Add a read-only Q&A agent + chat panel to the "Exec Summary" tab of the
live Alliant workbook (69b0edbc-751a-4ea5-840b-d2ceefef824d). Purely
additive: two new elements (a title text + a chat panel) appended to
document.elements, one new agent appended to document.agents, and a small
layout-XML insertion into Tab 1 of the tabbed container on page-exec, in the
free space below the existing KPI-change row. Nothing else in the document
is touched.

No new dataset -- the workbook already has 13 tables covering the topics an
executive would ask about (monthly enrollment/medical/pharmacy/total trend,
plan mix, place-of-service utilization, medical spend by category,
demographic spend/enrollment/claims, claim cost, cost per member,
member-paid split, waived/gender/tier/age/county mix), all broken out by
employer group. The agent is bound to all of them as read-only dataSources.

Usage: python3 add_exec_qa_agent.py verify   # dry run, no PUT
       python3 add_exec_qa_agent.py apply    # PUT the change
"""
import copy
import json
import sys

import sigmaapi as S

WORKBOOK_ID = "69b0edbc-751a-4ea5-840b-d2ceefef824d"

DATASOURCE_TABLES = [
    "tbl-monthly", "tbl-plan", "tbl-pos", "tbl-medc", "tbl-demo",
    "tbl-claim-cost", "tbl-cpm", "tbl-member-paid", "tbl-waived-split",
    "tbl-gender-split", "tbl-tier", "tbl-age", "tbl-county",
]

AGENT = {
    "id": "ag-exec-qa",
    "name": "Alliant Executive Insights",
    "description": (
        "Answers questions about Alliant's book of business -- enrollment, "
        "medical, pharmacy, and utilization performance across GEICO, FIS "
        "Global, and Contoso Logistics."
    ),
    "instructions": (
        "You are a benefits analyst assistant for Alliant Insurance's book "
        "of business (employer groups: GEICO, FIS Global, Contoso "
        "Logistics). Answer questions using ONLY the provided data sources: "
        "a monthly enrollment/medical/pharmacy/total spend trend (current "
        "vs prior period), plan mix, place-of-service utilization and PMPM, "
        "medical spend by category, spend/enrollment/claims by generation, "
        "gender and state, average claim cost, cost per member, member-paid "
        "vs plan-paid split, and waived-coverage/gender/coverage-tier/age-"
        "band/county mix -- each broken out by employer group where "
        "applicable. Always cite the specific number(s) behind your answer "
        "and name the employer group(s) involved. If a question needs data "
        "not present in these tables, say so plainly rather than guessing "
        "or inventing a number."
    ),
    "greeting": {
        "mode": "static",
        "message": (
            "Ask me anything about Alliant's enrollment, medical, "
            "pharmacy, or utilization performance -- for example, "
            "\"which group had the biggest medical spend increase?\" or "
            "\"what's driving the pharmacy trend?\""
        ),
    },
    "dataSources": [{"kind": "table", "elementId": t} for t in DATASOURCE_TABLES],
    "tools": [],
}

TITLE_ELEMENT = {
    "id": "txt-qa-title-exec",
    "kind": "text",
    "body": "**Ask About This Book of Business**",
    "style": {"backgroundColor": "transparent"},
}

CHAT_ELEMENT = {
    "id": "chat-exec-qa",
    "kind": "chat",
    "agentId": "ag-exec-qa",
}

# Inserted immediately before the Tab-1-closing </Tab> that follows the
# kpi-tot-chg-exec element -- i.e. right after the existing KPI-change row,
# in the tab's unused space below row 20.
LAYOUT_INSERT_AFTER = '<Element elementId="kpi-tot-chg-exec" gridColumn="10 / 13" gridRow="16 / 20"/>'
LAYOUT_INSERT = (
    '\n      <Element elementId="txt-qa-title-exec" gridColumn="1 / 13" gridRow="21 / 23"/>'
    '\n      <Element elementId="chat-exec-qa" gridColumn="1 / 13" gridRow="23 / 42"/>'
)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    assert mode in ("verify", "apply")

    spec = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")
    doc = spec["document"]

    # Safety: confirm the snapshot matches what was manually confirmed stable
    # (4 pages, 117 elements) right before this script was written. If the
    # user has since edited the workbook again, refuse rather than clobber it.
    page_ids = [p["id"] for p in doc.get("pages", [])]
    if page_ids != ["page-exec", "o5F5nuTOj9", "page-cohort", "page-data"]:
        print("REFUSING: page structure has changed since last verified.")
        print("Current pages:", page_ids)
        sys.exit(1)
    if len(doc.get("elements", [])) != 117:
        print("REFUSING: element count has changed since last verified "
              f"(now {len(doc.get('elements', []))}, expected 117).")
        sys.exit(1)

    orig_elements = copy.deepcopy(doc["elements"])
    orig_agents = copy.deepcopy(doc.get("agents"))
    orig_layout = doc["layout"]

    existing_ids = {e["id"] for e in orig_elements}
    for t in DATASOURCE_TABLES:
        if t not in existing_ids:
            print(f"REFUSING: dataSource table {t!r} not found in document.elements.")
            sys.exit(1)

    if LAYOUT_INSERT_AFTER not in orig_layout:
        print("REFUSING: expected anchor string not found in layout XML.")
        sys.exit(1)
    if orig_layout.count(LAYOUT_INSERT_AFTER) != 1:
        print("REFUSING: anchor string is not unique in layout XML.")
        sys.exit(1)

    new_doc = copy.deepcopy(doc)
    new_doc["elements"] = orig_elements + [TITLE_ELEMENT, CHAT_ELEMENT]
    new_doc["agents"] = (orig_agents or []) + [AGENT]
    new_doc["layout"] = orig_layout.replace(
        LAYOUT_INSERT_AFTER, LAYOUT_INSERT_AFTER + LAYOUT_INSERT, 1
    )

    print(f"Adding agent {AGENT['id']!r}, elements "
          f"{TITLE_ELEMENT['id']!r} + {CHAT_ELEMENT['id']!r}.")
    print(f"New element count: {len(new_doc['elements'])} "
          f"(was {len(orig_elements)}).")
    print(f"New agent count: {len(new_doc['agents'])} "
          f"(was {len(orig_agents or [])}).")

    if mode == "verify":
        body = {"name": spec["name"], "folderId": spec.get("folderId"),
                "document": new_doc}
        S.call("POST", "/v2/workbooks/spec/verify", body)
        print("verify: OK")
        return

    body = {"document": new_doc}
    S.call("PUT", f"/v2/workbooks/{WORKBOOK_ID}/spec", body)
    print("PUT: OK")

    # Re-fetch and confirm every pre-existing element is byte-identical, and
    # the rest of the layout is an exact substring match except for our one
    # insertion.
    back = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")["document"]
    back_by_id = {e["id"]: e for e in back["elements"]}
    mismatches = []
    for e in orig_elements:
        if back_by_id.get(e["id"]) != e:
            mismatches.append(e["id"])
    if mismatches:
        print("WARNING: these pre-existing elements changed on GET-back:", mismatches)
    else:
        print(f"Confirmed: all {len(orig_elements)} pre-existing elements "
              "are byte-identical after the PUT.")

    expected_layout = orig_layout.replace(
        LAYOUT_INSERT_AFTER, LAYOUT_INSERT_AFTER + LAYOUT_INSERT, 1
    )
    if back["layout"] == expected_layout:
        print("Confirmed: layout XML matches expected (old content + one insertion).")
    else:
        print("WARNING: layout XML does not exactly match the expected result.")

    back_agent_ids = [a["id"] for a in back.get("agents", [])]
    print("Agents after PUT:", back_agent_ids)


if __name__ == "__main__":
    main()
