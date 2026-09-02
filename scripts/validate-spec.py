#!/usr/bin/env python3
"""Pre-POST static validation for a Sigma workbook spec (2026-08 schema).

The Sigma POST/PUT endpoints accept structurally broken specs and silently
rewrite the layout — most notably, elements not placed in the layout XML
render at the page bottom or not at all, container children stack into a
1/13-wide single column when not nested in their `<Container>` in the
layout XML, and `format` on columns returns a misleading "Missing 'kind'
field" error.

Schema (verified 2026-08-07 on papercranestaging): everything except
`name`/`folderId` lives inside a `document{}` envelope; elements are a FLAT
`document.elements` list (no more `pages[].elements`); layout tags are
`<Element>`/`<Container>` (not `<LayoutElement>`/`<GridContainer>`).

Run before every POST/PUT:

    python3 scripts/validate-spec.py workbooks/<name>/spec.json

Exits 0 on success, non-zero on any issue (one issue per line on stderr).
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET


CHECKS = [
    "no-per-page-layout",
    "elements-placed-in-layout",
    "containers-have-children",
    "no-column-format",
    "control-id-unique",
    "no-legacy-layout-tags",
]


def issues_per_page_layout(doc: dict) -> list[str]:
    issues = []
    for i, p in enumerate(doc.get("pages", [])):
        if p.get("layout") or p.get("elements") is not None:
            issues.append(
                f"document.pages[{i}] ({p.get('id')}): has a per-page `layout` "
                "or `elements` field. Both are gone in the 2026-08 schema — "
                "elements live in the flat `document.elements` list, and "
                "layout is the single top-level `document.layout` string."
            )
    return issues


def _parse_layout(layout: str) -> ET.Element | None:
    if not layout:
        return None
    # Multi-page layout is multiple <Page> siblings under one <?xml ... ?> decl —
    # not a valid single-root XML doc. Wrap to parse.
    cleaned = re.sub(r"<\?xml[^?]*\?>", "", layout).strip()
    wrapped = f"<root>{cleaned}</root>"
    try:
        return ET.fromstring(wrapped)
    except ET.ParseError as e:
        sys.stderr.write(f"validate-spec: layout XML failed to parse: {e}\n")
        return None


def issues_legacy_tags(layout: str) -> list[str]:
    issues = []
    if re.search(r"<LayoutElement\b", layout):
        issues.append(
            "layout uses <LayoutElement> — renamed to <Element> in the "
            "2026-08 schema. The old tag name causes a masked 500, not a "
            "useful validation error."
        )
    if re.search(r"<GridContainer\b", layout):
        issues.append(
            "layout uses <GridContainer> — renamed to <Container> in the "
            "2026-08 schema. The old tag name causes a masked 500, not a "
            "useful validation error."
        )
    return issues


def issues_elements_placed(doc: dict, root: ET.Element | None) -> list[str]:
    if root is None:
        return ["no top-level `document.layout` field — workbook will have an auto-generated layout"]
    placed_ids = {
        el.get("elementId")
        for el in root.iter()
        if el.tag in ("Element", "Container", "TabbedContainer")
    }
    issues = []
    for el in doc.get("elements", []):
        eid = el.get("id")
        if eid and eid not in placed_ids:
            issues.append(
                f"document.elements ({eid}, kind={el.get('kind')}): "
                "not placed in the layout XML — will render at the page bottom or not at all."
            )
    return issues


def issues_containers_have_children(doc: dict, root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    container_ids = [el.get("id") for el in doc.get("elements", []) if el.get("kind") == "container"]
    issues = []
    for cid in container_ids:
        gc = next((el for el in root.iter("Container") if el.get("elementId") == cid), None)
        if gc is None:
            issues.append(
                f"container element `{cid}`: no matching <Container> in layout XML."
            )
        elif len(list(gc)) == 0:
            issues.append(
                f"container element `{cid}`: <Container> has no nested children. "
                "Children must be nested INSIDE the <Container>, not flat siblings."
            )
    return issues


def issues_no_format(doc: dict) -> list[str]:
    # NOTE: an older draft of this rule hard-failed any column `format`. The
    # verified build_cava.py exemplar uses format dicts with an explicit
    # `kind` (e.g. {"kind":"number","formatString":"$.3~s",...}) successfully,
    # so a `format` WITH a `kind` key is plausibly fine — only warn, don't fail.
    # A `format` MISSING `kind` matches the documented rejection; that stays fatal.
    issues = []
    for ei, el in enumerate(doc.get("elements", [])):
        for ci, col in enumerate(el.get("columns", []) or []):
            fmt = col.get("format")
            if fmt is None:
                continue
            if "kind" not in fmt:
                issues.append(
                    f"document.elements[{ei}].columns[{ci}] ({col.get('id')}): "
                    "`format` is missing `kind` — Sigma rejects with 'Missing \"kind\" field'."
                )
            else:
                sys.stderr.write(
                    f"[no-column-format] NOTE (non-fatal): document.elements[{ei}].columns[{ci}] "
                    f"({col.get('id')}) has format.kind={fmt.get('kind')!r} — verify it round-trips on GET.\n"
                )
    return issues


def issues_control_id_unique(doc: dict) -> list[str]:
    seen: dict[str, str] = {}
    issues = []
    for el in doc.get("elements", []):
        if el.get("kind") != "control":
            continue
        cid = el.get("controlId")
        if not cid:
            continue
        if cid in seen:
            issues.append(
                f"controlId `{cid}` duplicated on elements {seen[cid]} and {el.get('id')}. "
                "controlId is workbook-wide unique."
            )
        else:
            seen[cid] = el.get("id")
    return issues


def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate-spec.py <spec.json>\n")
        sys.exit(2)
    with open(sys.argv[1]) as f:
        spec = json.load(f)

    if "document" not in spec:
        sys.stderr.write(
            "validate-spec: no top-level `document` envelope. The 2026-08 schema "
            "wraps everything except name/folderId inside `document{}` — see "
            "skills/sigma-workbook-conventions/reference/schema-2026-08-breaking-changes.md\n"
        )
        sys.exit(1)

    doc = spec["document"]
    layout = doc.get("layout", "")
    root = _parse_layout(layout)

    all_issues: list[tuple[str, str]] = []
    for tag, fn in [
        ("no-per-page-layout",        lambda: issues_per_page_layout(doc)),
        ("no-legacy-layout-tags",     lambda: issues_legacy_tags(layout)),
        ("elements-placed-in-layout", lambda: issues_elements_placed(doc, root)),
        ("containers-have-children",  lambda: issues_containers_have_children(doc, root)),
        ("no-column-format",          lambda: issues_no_format(doc)),
        ("control-id-unique",         lambda: issues_control_id_unique(doc)),
    ]:
        for msg in fn():
            all_issues.append((tag, msg))

    if not all_issues:
        print(f"validate-spec: {sys.argv[1]} — all {len(CHECKS)} checks passed")
        sys.exit(0)

    for tag, msg in all_issues:
        sys.stderr.write(f"[{tag}] {msg}\n")
    sys.stderr.write(f"\nvalidate-spec: {len(all_issues)} issue(s) found in {sys.argv[1]}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
