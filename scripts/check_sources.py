#!/usr/bin/env python3
"""Verify sources/catalog.yaml evidence paths exist."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "sources" / "catalog.yaml"


def main() -> int:
    data = yaml.safe_load(CAT.read_text(encoding="utf-8")) or {}
    problems: list[str] = []
    entries = data.get("entries") or []
    print(f"JarvisLab sources ({len(entries)} entries)")
    for e in entries:
        eid = e.get("id")
        status = e.get("status")
        print(f"  [{status}] {eid} {e.get('url')}")
        if status != "integrated":
            continue
        for rel in e.get("evidence") or []:
            if not (ROOT / rel).exists():
                problems.append(f"{eid}: missing {rel}")
    if problems:
        print("FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
