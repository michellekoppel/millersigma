#!/usr/bin/env python3
"""Expand the Open/Reopened cohort rows (at latest valuation) from gen_data.py
into individual synthetic claim records, for the Reserve Review Workbench.
Same seed/source numbers as the main dataset -- these are the same claims,
just disaggregated to claim grain for a realistic review queue.
"""
import random
import datetime
import sys

sys.path.insert(0, "/tmp/claude-0/-home-user-millersigma/4706fb90-7ebb-51e4-87f3-b8ea4078388e/scratchpad")
from gen_data import gen_claims_rows, CLAIMS_COLUMNS, sql_literal, Raw
# NOTE: gen_data sets random.seed(42) at import time. Do NOT reseed here --
# gen_claims_rows() must reproduce the exact same cohort totals already
# live in tbl-claims. The splitting below just continues consuming the same
# random stream afterward, which is fine (gen_claims_rows() has already
# finished by the time split_amount() runs).

LOB_ABBR = {
    "Workers Comp": "WC",
    "General Liability": "GL",
    "Commercial Auto": "AU",
    "Property": "PR",
}

AS_OF = datetime.date(2026, 9, 1)


def split_amount(total, n, jitter=0.6):
    """Split `total` across n positive, randomly-sized shares that sum
    exactly to `total` (Dirichlet-style via random weights)."""
    if n <= 0:
        return []
    weights = [max(0.05, random.gauss(1.0, jitter)) for _ in range(n)]
    s = sum(weights)
    shares = [total * w / s for w in weights]
    return shares


def gen_claim_queue_rows():
    idx = CLAIMS_COLUMNS.index
    claims = gen_claims_rows()
    seq_by_lob = {}
    rows = []
    for r in claims:
        if r[idx("is_latest_valuation")] != 1:
            continue
        status = r[idx("claim_status")]
        if status not in ("Open", "Reopened"):
            continue
        py = r[idx("policy_year")]
        lob = r[idx("line_of_business")]
        n = r[idx("claim_count")]
        paid_total = r[idx("paid_loss")] or 0.0
        reserve_total = r[idx("case_reserve")] or 0.0
        if n <= 0:
            continue
        paid_shares = split_amount(paid_total, n)
        reserve_shares = split_amount(reserve_total, n)
        for i in range(n):
            seq_by_lob[lob] = seq_by_lob.get(lob, 0) + 1
            claim_id = f"{LOB_ABBR[lob]}-{py}-{seq_by_lob[lob]:04d}"
            paid = round(paid_shares[i], 2)
            reserve = round(reserve_shares[i], 2)
            incurred = round(paid + reserve, 2)
            # reported some months into the policy year; days open = since then
            reported = datetime.date(py, random.randint(1, 12), random.randint(1, 28))
            days_open = max(1, (AS_OF - reported).days)
            rows.append((
                claim_id, py, lob, status, paid, reserve, incurred,
                days_open, reported.isoformat(),
            ))
    return rows


COLUMNS = [
    "claim_id", "policy_year", "line_of_business", "claim_status",
    "paid_to_date", "case_reserve", "incurred", "days_open", "reported_date",
]


def rows_to_values_sql(rows):
    lits = []
    for r in rows:
        vals = list(r)
        vals[-1] = Raw(f"DATE '{r[-1]}'")
        lits.append("(" + ", ".join(sql_literal(v) for v in vals) + ")")
    return ",\n    ".join(lits)


if __name__ == "__main__":
    rows = gen_claim_queue_rows()
    print(f"-- claim queue rows: {len(rows)}")
    tot_reserve = sum(r[5] for r in rows)
    print(f"-- total reserve under review: {tot_reserve:,.0f}")
    by_status = {}
    for r in rows:
        by_status[r[3]] = by_status.get(r[3], 0) + 1
    print("-- by status:", by_status)
    SCRATCH = "/tmp/claude-0/-home-user-millersigma/4706fb90-7ebb-51e4-87f3-b8ea4078388e/scratchpad"
    with open(f"{SCRATCH}/claim_queue_values.sql", "w") as f:
        f.write(rows_to_values_sql(rows))
    print("wrote claim_queue_values.sql")
