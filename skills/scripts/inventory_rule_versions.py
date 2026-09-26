#!/usr/bin/env python3
"""Inventory portable skill-rule Markdown; hashes never prove reading or compliance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

SCHEMA_VERSION = 1
SCOPE = "skill_rule_markdown_v1"
STATUS = "inventory_only_content_reading_required"


def rule_paths(root: Path) -> list[Path]:
    """Discover rule sources, excluding scripts, assets, UI metadata and outer rules."""
    if not root.is_dir() or not (root / "AGENTS.md").is_file():
        raise ValueError("Expected a skills root containing AGENTS.md")
    if not (root / "shared-references" / "rule_authority_index.md").is_file():
        raise ValueError("Missing rule authority index")
    if not list(root.glob("*/SKILL.md")):
        raise ValueError("No SKILL.md entrypoints found")
    paths = []
    for path in sorted(root.rglob("*.md")):
        parts = path.relative_to(root).parts
        selected = (
            parts == ("AGENTS.md",)
            or (len(parts) == 2 and parts[1] == "SKILL.md")
            or parts[0] == "shared-references"
            or (len(parts) > 2 and parts[1] == "references")
        )
        if not selected or any(p in {"assets", "scripts"} or p.startswith(".") for p in parts):
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"Rule source escapes root or is not a file: {path}")
        paths.append(path)
    return paths


def rules_hash(rows: list[dict]) -> str:
    pairs = sorted((row["relative_path"], row["sha256"]) for row in rows)
    data = json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict:
    root = root.resolve(strict=True)
    rows = []
    for path in rule_paths(root):
        data = path.read_bytes()
        content = data.decode("utf-8-sig")
        if not content.strip():
            raise ValueError(f"Empty rule source: {path.relative_to(root)}")
        rows.append({
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "lines": len(content.splitlines()),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "status": STATUS,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "skill_root": str(root),
        "rules_sha256": rules_hash(rows),
        "files": rows,
    }


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_previous(path: Path, root: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ValueError("Invalid rule inventory schema")
    if data["schema_version"] != SCHEMA_VERSION or data.get("scope") != SCOPE:
        raise ValueError("Unsupported rule inventory schema or scope")
    previous_root = data.get("skill_root")
    if not isinstance(previous_root, str) or not Path(previous_root).is_absolute():
        raise ValueError("Previous inventory must identify an absolute skills root")
    if Path(previous_root).resolve() != root:
        raise ValueError("Previous inventory belongs to a different skills root; review source change explicitly")
    rows = data.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Previous inventory has no valid file list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid previous file entry")
        name, digest = row.get("relative_path"), row.get("sha256")
        if not isinstance(name, str) or not name or "\\" in name:
            raise ValueError("Invalid relative rule path")
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or ":" in name or relative.as_posix() != name:
            raise ValueError("Noncanonical relative rule path")
        if name in seen:
            raise ValueError(f"Duplicate previous rule path: {name}")
        seen.add(name)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid previous content hash")
    if data.get("rules_sha256") != rules_hash(rows):
        raise ValueError("Previous inventory checksum is inconsistent")
    return data


def compare(current: dict, previous: dict | None) -> dict:
    old = {r["relative_path"]: r["sha256"] for r in previous["files"]} if previous else {}
    now = {r["relative_path"]: r["sha256"] for r in current["files"]}
    changes = {
        "added": sorted(now.keys() - old.keys()),
        "modified": sorted(k for k in now.keys() & old.keys() if now[k] != old[k]),
        "removed": sorted(old.keys() - now.keys()),
        "unchanged": sorted(k for k in now.keys() & old.keys() if now[k] == old[k]),
    }
    return {
        **current,
        "comparison": "same_root" if previous else "initial_inventory",
        "previous_recorded_at": previous.get("recorded_at") if previous else None,
        "changes": changes,
        "counts": {key: len(value) for key, value in changes.items()},
    }


def write_record(output: Path, report: dict, previous: Path | None = None) -> None:
    if output.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    target = output.resolve()
    root = Path(report["skill_root"])
    if target.is_relative_to(root):
        raise ValueError("Inventory output must be outside the skill installation")
    if target.suffix.lower() != ".json":
        raise ValueError("Inventory output must be a .json file")
    if target.exists() and (previous is None or previous.resolve() != target):
        raise ValueError("Existing output may only be replaced when explicitly used as --previous")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, prefix=target.name + ".",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--previous", type=Path, help="Explicit previous inventory; missing/corrupt records fail")
    parser.add_argument("--output", type=Path, help="Optional JSON record outside the skills root")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        current = inventory(args.root)
        previous = load_previous(args.previous, Path(current["skill_root"])) if args.previous else None
        report = compare(current, previous)
        if args.output:
            write_record(args.output, report, args.previous)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
