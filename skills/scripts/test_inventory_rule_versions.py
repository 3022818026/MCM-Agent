#!/usr/bin/env python3
"""Behavioral tests for rule inventories; fixtures never mutate installed skills."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from inventory_rule_versions import compare, inventory, load_previous, rules_hash, write_record

SCRIPT = Path(__file__).with_name("inventory_rule_versions.py")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rule_inventory_")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "含空格 skills"
        self.root.mkdir()
        self.put("AGENTS.md", "# Rules\n")
        self.put("shared-references/rule_authority_index.md", "# Index\n")
        self.put("demo/SKILL.md", "---\nname: demo\ndescription: demo\n---\n")
        self.put("demo/references/检查.md", "# 内容\n")
        self.record = self.base / "项目记录" / "rules.json"

    def put(self, relative, content):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *map(str, args)],
                              capture_output=True, encoding="utf-8")

    def test_initial_cli_is_read_only_and_handles_unicode(self):
        before = sorted(str(p) for p in self.base.rglob("*"))
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["counts"], {"added": 4, "modified": 0, "removed": 0, "unchanged": 0})
        self.assertEqual(report["status"], "inventory_only_content_reading_required")
        self.assertEqual(before, sorted(str(p) for p in self.base.rglob("*")))

    def test_added_modified_removed_and_unchanged(self):
        self.put("demo/references/检查.md", "# 修改\n")
        self.put("demo/references/new.md", "# New\n")
        (self.root / "AGENTS.md").write_text("# New rules\n", encoding="utf-8")
        self.put("shared-references/old.md", "# old\n")
        old = inventory(self.root)
        self.put("demo/references/检查.md", "# 再改\n")
        self.put("shared-references/new.md", "# new\n")
        (self.root / "shared-references/old.md").unlink()
        report = compare(inventory(self.root), old)
        self.assertEqual(report["changes"]["modified"], ["demo/references/检查.md"])
        self.assertEqual(report["changes"]["added"], ["shared-references/new.md"])
        self.assertEqual(report["changes"]["removed"], ["shared-references/old.md"])
        self.assertEqual(len(report["changes"]["unchanged"]), 4)

    def test_hash_detects_same_size_same_mtime_edit(self):
        source = self.put("shared-references/sample.md", "alpha")
        old = inventory(self.root)
        stat = source.stat()
        source.write_text("bravo", encoding="utf-8")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = compare(inventory(self.root), old)
        self.assertEqual(report["changes"]["modified"], ["shared-references/sample.md"])

    def test_asset_and_code_changes_do_not_claim_rule_changes(self):
        old = inventory(self.root)
        self.put("demo/assets/example.md", "not a rule")
        self.put("scripts/code.py", "print('example')")
        self.put("demo/agents/openai.yaml", "interface: {}")
        report = compare(inventory(self.root), old)
        self.assertEqual(report["counts"], {"added": 0, "modified": 0, "removed": 0, "unchanged": 4})

    def test_output_then_explicit_same_file_update(self):
        first = self.cli("--output", self.record)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.put("demo/references/检查.md", "# 新版\n")
        second = self.cli("--previous", self.record, "--output", self.record)
        self.assertEqual(second.returncode, 0, second.stderr)
        saved = json.loads(self.record.read_text(encoding="utf-8"))
        self.assertEqual(saved["changes"]["modified"], ["demo/references/检查.md"])
        third = self.cli("--previous", self.record)
        self.assertEqual(json.loads(third.stdout)["counts"]["unchanged"], 4)
        self.assertFalse(list(self.record.parent.glob("*.tmp")))

    def test_missing_previous_does_not_silently_reset(self):
        result = self.cli("--previous", self.record, "--output", self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.record.exists())
        self.assertFalse(result.stdout.strip())

    def test_corrupt_previous_preserved_on_failed_update(self):
        self.record.parent.mkdir()
        self.record.write_bytes(b'{"broken"')
        result = self.cli("--previous", self.record, "--output", self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record.read_bytes(), b'{"broken"')

    def test_different_root_rejected(self):
        report = inventory(self.root)
        report["skill_root"] = str(self.base / "other skills")
        self.record.parent.mkdir(exist_ok=True)
        self.record.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_previous(self.record, self.root.resolve())

    def test_duplicate_rows_and_bad_checksum_rejected(self):
        self.record.parent.mkdir()
        for kind in ("duplicate", "checksum", "traversal", "schema"):
            report = inventory(self.root)
            if kind == "duplicate":
                report["files"].append(dict(report["files"][0]))
                report["rules_sha256"] = rules_hash(report["files"])
            elif kind == "checksum":
                report["files"][0]["sha256"] = hashlib.sha256(b"other").hexdigest()
            elif kind == "traversal":
                report["files"][0]["relative_path"] = "../outside.md"
                report["rules_sha256"] = rules_hash(report["files"])
            else:
                report["schema_version"] = True
            self.record.write_text(json.dumps(report), encoding="utf-8")
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                load_previous(self.record, self.root.resolve())

    def test_duplicate_json_keys_rejected(self):
        self.record.parent.mkdir()
        self.record.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_previous(self.record, self.root.resolve())

    def test_empty_rule_is_error_not_removal(self):
        self.put("demo/references/检查.md", " \n")
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout.strip())

    def test_writes_inside_installation_and_unrelated_overwrite_rejected(self):
        report = compare(inventory(self.root), None)
        with self.assertRaises(ValueError):
            write_record(self.root / "snapshot.json", report)
        self.record.parent.mkdir()
        self.record.write_text("unrelated", encoding="utf-8")
        with self.assertRaises(ValueError):
            write_record(self.record, report)
        self.assertEqual(self.record.read_text(encoding="utf-8"), "unrelated")

    def test_external_rule_symlink_rejected(self):
        outside = self.base / "outside.md"
        outside.write_text("# external\n", encoding="utf-8")
        link = self.root / "demo/references/linked.md"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        with self.assertRaises(ValueError):
            inventory(self.root)


if __name__ == "__main__":
    unittest.main()
