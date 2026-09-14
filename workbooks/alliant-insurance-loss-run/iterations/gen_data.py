#!/usr/bin/env python3
"""Generate the two literal-VALUES SQL statements for the Alliant loss-run
workbook: one large claims fact table + one small premium reference table.
Pure synthetic/illustrative numbers, no real Alliant data.
"""
import random

random.seed(42)

POLICY_YEARS = list(range(2019, 2026))  # 2019..2025
LOBS = ["Workers Comp", "General Liability", "Commercial Auto", "Property"]
STATUSES = ["Open", "Closed", "Reopened"]

# As-of valuation date: Q3 2026. Dev periods (months) available per policy
# year, truncated so the table is a REAL triangle (recent years only have
# early development), not padded/flat.
AS_OF_YEAR = 2026
DEV_GRID = [12, 24, 36, 48, 60, 72, 84]

# LOB shape parameters: ultimate loss ratio target, tail length (how slowly
# it develops), and base claim frequency per 100 policies.
LOB_PARAMS = {
    "Workers Comp":      dict(base_prem=6_200_000, ult_lr=0.68, tail=0.34, freq=9,  sev=28_000, policies=1050),
    "General Liability": dict(base_prem=3_400_000, ult_lr=0.58, tail=0.30, freq=4,  sev=42_000, policies=760),
    "Commercial Auto":   dict(base_prem=4_100_000, ult_lr=0.72, tail=0.22, freq=14, sev=19_000, policies=980),
    "Property":          dict(base_prem=5_000_000, ult_lr=0.52, tail=0.12, freq=6,  sev=31_000, policies=890),
}

# Status mix by maturity bucket (fraction of open claim_count that is
# Open / Closed / Reopened at each dev period rung, 1..7).
STATUS_MIX = {
    1: {"Open": 0.86, "Closed": 0.10, "Reopened": 0.04},
    2: {"Open": 0.62, "Closed": 0.32, "Reopened": 0.06},
    3: {"Open": 0.40, "Closed": 0.53, "Reopened": 0.07},
    4: {"Open": 0.24, "Closed": 0.69, "Reopened": 0.07},
    5: {"Open": 0.14, "Closed": 0.80, "Reopened": 0.06},
    6: {"Open": 0.08, "Closed": 0.87, "Reopened": 0.05},
    7: {"Open": 0.05, "Closed": 0.91, "Reopened": 0.04},
}


def dev_curve(rung_idx: int, tail: float) -> float:
    """Fraction of ultimate loss emerged by this development rung (1..7),
    a simple saturating curve; `tail` controls how slowly it approaches 1."""
    months = DEV_GRID[rung_idx - 1]
    return 1 - (1 - tail) ** (months / 12.0)


class Raw(str):
    """Marker: emit verbatim in SQL, no quoting."""


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def join_key(py, lob):
    return f"{py}|{lob}"


def year_date(py):
    return Raw(f"DATE '{py}-01-01'")


# Within a status bucket, the fraction of that bucket's incurred dollars
# that has actually been PAID out (rest sits in case reserve). Closed
# claims are by definition fully paid.
STATUS_PAID_FRAC = {"Open": 0.45, "Closed": 1.0, "Reopened": 0.40}


def gen_claims_rows():
    rows = []
    for py in POLICY_YEARS:
        years_elapsed = AS_OF_YEAR - py
        max_rung = min(len(DEV_GRID), max(1, years_elapsed))
        for lob in LOBS:
            p = LOB_PARAMS[lob]
            ultimate_incurred = p["base_prem"] * p["ult_lr"] * random.uniform(0.94, 1.06)
            ultimate_claims = round(p["policies"] * (p["freq"] / 100.0) * random.uniform(0.92, 1.08))
            for rung in range(1, max_rung + 1):
                dev = DEV_GRID[rung - 1]
                frac_now = dev_curve(rung, p["tail"])
                incurred_to_date = ultimate_incurred * frac_now
                claims_to_date = round(ultimate_claims * min(1.0, frac_now + 0.15))
                mix = STATUS_MIX[rung]
                valuation_year = py + dev // 12
                is_latest = 1 if rung == max_rung else 0
                for status, frac in mix.items():
                    claim_count = round(claims_to_date * frac)
                    if claim_count <= 0:
                        continue
                    # Split incurred dollars by claim-count share (each status'
                    # slice of the pie), then split that slice into paid/reserve
                    # so paid+reserve reconstructs incurred exactly.
                    status_incurred = incurred_to_date * frac
                    paid = status_incurred * STATUS_PAID_FRAC[status]
                    reserve = status_incurred - paid
                    rows.append((
                        "CLAIM", py, lob, status, dev, valuation_year,
                        None, round(paid, 2), round(reserve, 2), claim_count, None, is_latest,
                        join_key(py, lob), year_date(py),
                    ))
    return rows


def gen_premium_rows():
    rows = []
    for py in POLICY_YEARS:
        for lob in LOBS:
            p = LOB_PARAMS[lob]
            premium = p["base_prem"] * random.uniform(0.97, 1.03) * (1 + 0.02 * (py - 2019))
            policies = round(p["policies"] * random.uniform(0.96, 1.04))
            rows.append((
                "PREMIUM", py, lob, None, None, None,
                round(premium, 2), None, None, None, policies,
                join_key(py, lob), year_date(py),
            ))
    return rows


CLAIMS_COLUMNS = [
    "row_type", "policy_year", "line_of_business", "claim_status",
    "dev_period_months", "valuation_year", "earned_premium",
    "paid_loss", "case_reserve", "claim_count", "policy_count",
    "is_latest_valuation", "join_key", "policy_year_date",
]
PREMIUM_COLUMNS = [
    "row_type", "policy_year", "line_of_business", "claim_status",
    "dev_period_months", "valuation_year", "earned_premium",
    "paid_loss", "case_reserve", "claim_count", "policy_count",
    "join_key", "policy_year_date",
]


def rows_to_values_sql(rows):
    lines = []
    for r in rows:
        lines.append("(" + ", ".join(sql_literal(v) for v in r) + ")")
    return ",\n    ".join(lines)


if __name__ == "__main__":
    claims = gen_claims_rows()
    premium = gen_premium_rows()
    print(f"-- claims rows: {len(claims)}", flush=True)
    print(f"-- premium rows: {len(premium)}", flush=True)

    SCRATCH = "/tmp/claude-0/-home-user-millersigma/4706fb90-7ebb-51e4-87f3-b8ea4078388e/scratchpad"
    with open(f"{SCRATCH}/claims_values.sql", "w") as f:
        f.write(rows_to_values_sql(claims))
    with open(f"{SCRATCH}/premium_values.sql", "w") as f:
        f.write(rows_to_values_sql(premium))

    # sanity totals -- latest-diagonal only, matching how the workbook
    # actually aggregates "current" incurred (via is_latest_valuation mask)
    li = CLAIMS_COLUMNS.index("is_latest_valuation")
    tot_incurred = sum((r[7] or 0) + (r[8] or 0) for r in claims if r[li] == 1)
    tot_paid = sum((r[7] or 0) for r in claims if r[li] == 1)
    tot_claims = sum((r[9] or 0) for r in claims if r[li] == 1)
    tot_prem = sum(r[6] or 0 for r in premium)
    print(f"-- total incurred (latest diagonal): {tot_incurred:,.0f}")
    print(f"-- total paid     (latest diagonal): {tot_paid:,.0f}")
    print(f"-- total claim count (latest):       {tot_claims:,.0f}")
    print(f"-- total premium:                    {tot_prem:,.0f}")
    print(f"-- overall LR:                       {tot_incurred/tot_prem:.1%}")
    print(f"-- avg severity:                     {tot_incurred/tot_claims:,.0f}")
