"""Make the saved-cohort picker (ctrl-cohort-pick, on the "Cohort Viz" tab)
actually drive the distribution charts/table, per the user's explicit
requirement: "if the saved cohort picker has a value, then those charts
should reflect the data in that cohort."

Why this needed more than a formula: bar-cohort-pmpmdist / bar-cohort-
agedist / tbl-cohort-topn all read live from tbl-cohort-pop, filtered ONLY
by the 7 controls on the "Cohort Builder" tab (Coverage Tier, Age Band,
Gender, Relationship, Plan, Tenure, Group). The Save action only ever
persisted AGGREGATE stats (size, total/avg PMPM, a few counts) -- never
which members were in a cohort, and `insert-rows` can't bulk-snapshot 2,000
rows in one action anyway. So there was no way to reconstruct "who was in
cohort X" after the fact for a distribution/detail-level view.

The fix: capture the filter CRITERIA (not raw Text() of a multi-select,
which is a documented-broken read) as agent-authored plain text at save
time -- the agent already knows what it just set from its own conversation
turn, no formula read-back needed. Add a "Load a saved cohort" tool that
reads those stored criteria back and re-applies them to the SAME 7 live
controls the charts already filter by, via clear-control + set-control-
value. No changes needed to the charts themselves -- they inherit
whatever the controls are set to, same mechanism as always.

Purely additive: 7 new text columns on input-cohort-saved (kind: plain
input-table, no layout placement needed for columns), one new agent tool,
2 tool-description/instructions edits, 1 new agent dataSource. No layout
XML changes at all.

Usage: python3 add_cohort_load_feature.py verify   # dry run, no PUT
       python3 add_cohort_load_feature.py apply    # PUT the change
"""
import copy
import sys

import sigmaapi as S

WORKBOOK_ID = "69b0edbc-751a-4ea5-840b-d2ceefef824d"

NEW_SAVED_COLUMNS = [
    {"id": "s-tier", "type": "text", "name": "Tier Filter"},
    {"id": "s-age", "type": "text", "name": "Age Filter"},
    {"id": "s-gender", "type": "text", "name": "Gender Filter"},
    {"id": "s-rel", "type": "text", "name": "Relationship Filter"},
    {"id": "s-plan", "type": "text", "name": "Plan Filter"},
    {"id": "s-tenure", "type": "text", "name": "Tenure Filter"},
    {"id": "s-group", "type": "text", "name": "Group Filter"},
]

SAVE_INPUT_NAME = {
    "s-tier": "Coverage tier(s) currently filtered, comma-separated exactly as shown (e.g. 'Family'), or empty string if none set",
    "s-age": "Age band(s) currently filtered, comma-separated (e.g. '50-64, 65+'), or empty string if none set",
    "s-gender": "Gender(s) currently filtered, comma-separated, or empty string if none set",
    "s-rel": "Relationship(s) currently filtered, comma-separated, or empty string if none set",
    "s-plan": "Plan(s) currently filtered, comma-separated (e.g. 'Plan 2'), or empty string if none set",
    "s-tenure": "Enrollment tenure band(s) currently filtered, comma-separated, or empty string if none set",
    "s-group": "Employer group(s) currently filtered, comma-separated, or empty string if none set",
}

LOAD_CONTROL_FOR_COLUMN = {
    "s-tier": "CoverageTier",
    "s-age": "AgeBand",
    "s-gender": "Gender",
    "s-rel": "Relationship",
    "s-plan": "Plan",
    "s-tenure": "Tenure",
    "s-group": "GroupName",
}

LOAD_INPUT_NAME = {
    "s-tier": "Coverage tier value(s) stored in this cohort's 'Tier Filter' column, split on commas -- pass an empty list if that column was blank",
    "s-age": "Age band value(s) stored in 'Age Filter', split on commas -- empty list if blank",
    "s-gender": "Gender value(s) stored in 'Gender Filter', split on commas -- empty list if blank",
    "s-rel": "Relationship value(s) stored in 'Relationship Filter', split on commas -- empty list if blank",
    "s-plan": "Plan value(s) stored in 'Plan Filter', split on commas -- empty list if blank",
    "s-tenure": "Tenure value(s) stored in 'Tenure Filter', split on commas -- empty list if blank",
    "s-group": "Group value(s) stored in 'Group Filter', split on commas -- empty list if blank",
}

NEW_INSTRUCTIONS = (
    "You are a benefits/population-segmentation assistant for Alliant's book of business "
    "(GEICO, FIS Global, and Contoso Logistics). Help an analyst build a member cohort by "
    "setting filters -- coverage tier, age band, gender, relationship, plan, enrollment "
    "tenure, and group name -- based on natural language. Never assume a constraint the "
    "user didn't specify; leave it unset. After each change, confirm the resulting cohort "
    "size and average PMPM cost, and compare it to the baseline (the full book of business) "
    "so the user can see how selective the cohort is. Proactively propose and set a short "
    "cohort name and description as soon as the first filter is applied or changed -- keep "
    "them in sync with the current filters throughout the conversation; don't wait for the "
    "user to ask for a name. When the user asks to save, use the save tool -- state each "
    "filter's currently-selected value(s) yourself (you already know this from the "
    "conversation; don't try to read it back from a control) so the cohort can be reloaded "
    "later. When the user asks to load, reload, switch to, or pull up a previously saved "
    "cohort by name, look up that row in the Saved Cohorts data source, read its Tier/Age/"
    "Gender/Relationship/Plan/Tenure/Group Filter columns, and use the load tool to restore "
    "those exact values to the live filters -- split each stored value on commas, or pass "
    "an empty list for any column that was blank. After loading, confirm the resulting live "
    "cohort size matches the cohort's saved 'Size at Save Time' as a sanity check."
)

SAVE_DESCRIPTION = (
    "When the user asks to save/persist/record the current cohort, insert it into the "
    "Saved Cohorts log with its live size, PMPM cost, demographic snapshot, and the exact "
    "filter criteria currently applied (so it can be reloaded later)."
)

LOAD_DESCRIPTION = (
    "When the user asks to load, reload, switch to, or pull up a previously saved cohort "
    "by name, restore its exact filter criteria (read from the Saved Cohorts data source) "
    "to the live Coverage Tier / Age Band / Gender / Relationship / Plan / Tenure / Group "
    "filters, so every 'Current Cohort' chart and table reflects that saved cohort again."
)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    assert mode in ("verify", "apply")

    spec = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")
    doc = spec["document"]

    if len(doc.get("elements", [])) != 103 or len(doc.get("agents", [])) != 2:
        print(f"REFUSING: doc shape changed since last verified "
              f"(elements={len(doc.get('elements', []))}, agents={len(doc.get('agents', []))}, "
              f"expected 103/2).")
        sys.exit(1)

    new_doc = copy.deepcopy(doc)

    # 1. Extend input-cohort-saved with the 7 new text columns.
    saved_el = next(e for e in new_doc["elements"] if e["id"] == "input-cohort-saved")
    existing_col_ids = {c["id"] for c in saved_el["columns"]}
    for col in NEW_SAVED_COLUMNS:
        if col["id"] in existing_col_ids:
            print(f"REFUSING: column {col['id']!r} already exists on input-cohort-saved.")
            sys.exit(1)
    saved_el["columns"] = saved_el["columns"] + NEW_SAVED_COLUMNS

    # 2. Extend the agent: dataSources, save tool, new load tool, instructions.
    agent = next(a for a in new_doc["agents"] if a["id"] == "ag-cohort-builder")
    agent["instructions"] = NEW_INSTRUCTIONS

    if not any(ds.get("elementId") == "input-cohort-saved" for ds in agent["dataSources"]):
        agent["dataSources"] = agent["dataSources"] + [
            {"kind": "table", "elementId": "input-cohort-saved"}
        ]

    save_tool = next(t for t in agent["tools"] if t["toolId"] == "t-coh-save")
    save_tool["description"] = SAVE_DESCRIPTION
    insert_step = next(s for s in save_tool["steps"] if s["effect"] == "insert-rows")
    for col in NEW_SAVED_COLUMNS:
        cid = col["id"]
        insert_step["values"][cid] = {
            "type": "agent-input",
            "inputName": SAVE_INPUT_NAME[cid],
        }

    load_steps = []
    for col in NEW_SAVED_COLUMNS:
        cid = col["id"]
        control = LOAD_CONTROL_FOR_COLUMN[cid]
        load_steps.append({
            "kind": "effect",
            "effect": "clear-control",
            "scope": {"type": "control", "control": control},
        })
        load_steps.append({
            "kind": "effect",
            "effect": "set-control-value",
            "control": control,
            "selectionMode": "add",
            "value": {"type": "agent-input", "inputName": LOAD_INPUT_NAME[cid]},
        })

    if not any(t["toolId"] == "t-coh-load" for t in agent["tools"]):
        agent["tools"] = agent["tools"] + [{
            "toolId": "t-coh-load",
            "kind": "action",
            "name": "Load a saved cohort's filters",
            "description": LOAD_DESCRIPTION,
            "steps": load_steps,
        }]

    print("Adding 7 filter-criteria columns to Saved Cohorts, a new "
          "'Load a saved cohort's filters' agent tool, and updated "
          "save-tool/instructions. No layout changes.")

    if mode == "verify":
        S.call("POST", "/v2/workbooks/spec/verify",
               {"name": spec["name"], "folderId": spec.get("folderId"), "document": new_doc})
        print("verify: OK")
        return

    S.call("PUT", f"/v2/workbooks/{WORKBOOK_ID}/spec", {"document": new_doc})
    print("PUT: OK")

    back = S.call("GET", f"/v2/workbooks/{WORKBOOK_ID}/spec")["document"]
    back_by_id = {e["id"]: e for e in back["elements"]}
    other_elements = [e for e in doc["elements"] if e["id"] != "input-cohort-saved"]
    mismatches = [e["id"] for e in other_elements if back_by_id.get(e["id"]) != e]
    if not mismatches:
        print(f"Confirmed: all {len(other_elements)} other elements byte-identical.")
    else:
        print("NOTE: element diff (may be the known benign round-trip normalization):",
              mismatches)

    saved_back = back_by_id.get("input-cohort-saved")
    got_cols = {c["id"] for c in saved_back["columns"]}
    if all(c["id"] in got_cols for c in NEW_SAVED_COLUMNS):
        print("Confirmed: all 7 new columns present on input-cohort-saved.")
    else:
        print("WARNING: some new columns missing after PUT.")

    back_agent = next(a for a in back["agents"] if a["id"] == "ag-cohort-builder")
    print("Agent tools now:", [t["toolId"] for t in back_agent["tools"]])
    print("Agent dataSources now:", [ds.get("elementId") for ds in back_agent["dataSources"]])


if __name__ == "__main__":
    main()
