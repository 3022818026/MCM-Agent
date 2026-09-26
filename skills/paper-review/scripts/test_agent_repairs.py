#!/usr/bin/env python3
"""Behavioral regression tests; all mutations stay in a disposable fixture tree."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audit_under_test', HERE / 'audit_paper_integrity.py')
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)
SKILLS = ['data-preparation','figure-generation','model-evaluation','model-implementation','modeling-design','modeling-scientist','paper-review','paper-writing']

class NumericTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent_numeric_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / 'registry.json'
        self.registry.write_text('{"profit":100}', encoding='utf-8')
    def compare(self, output, registry=None, suffix='.json'):
        if registry is not None:
            self.registry.write_text(json.dumps(registry), encoding='utf-8')
        path = self.root / ('output' + suffix)
        path.write_text(output if isinstance(output,str) else json.dumps(output), encoding='utf-8')
        coverage = {}
        findings = audit.compare_results(self.registry, [path], 1e-8, coverage)
        return findings, coverage
    def test_equal_json_passes_with_coverage(self):
        f,c = self.compare({'profit':100})
        self.assertEqual(f,[])
        self.assertEqual((c['status'],c['matched_fields']),('passed',1))
    def test_json_mismatch_blocked(self):
        f,c = self.compare({'profit':999})
        self.assertEqual(c['status'],'failed')
    def test_csv_mismatch_blocked(self):
        f,c = self.compare('profit\n999\n',suffix='.csv')
        self.assertEqual(c['status'],'failed')
    def test_csv_equal_passes(self):
        f,c = self.compare('profit\n1e2\n',suffix='.csv')
        self.assertEqual(f,[])
    def test_records_match_by_id_not_order(self):
        rows = [{'result_id':'q1','value':100},{'result_id':'q2','value':200}]
        f,c = self.compare(list(reversed(rows)), {'results':rows})
        self.assertEqual(f,[])
        self.assertEqual(c['matched_fields'],2)
    def test_repeated_value_field_mismatch(self):
        f,c = self.compare({'result_id':'q1','value':999},{'results':[{'result_id':'q1','value':100},{'result_id':'q2','value':200}]})
        self.assertEqual(c['status'],'failed')
    def test_record_csv_cross_format(self):
        f,c = self.compare('result_id,metric,value\nq2,loss,200\nq1,loss,100\n',
                           {'results':[{'result_id':'q1','metric':'loss','value':100},{'result_id':'q2','metric':'loss','value':200}]}, '.csv')
        self.assertEqual(f,[])
    def test_full_paths_not_leaf_names(self):
        f,c = self.compare({'other':{'profit':100}}, {'model':{'profit':100}})
        self.assertEqual(c['matched_fields'],0)
        self.assertEqual(c['status'],'not_checked')
        self.assertTrue(f)
    def test_nan_and_inf_blocked(self):
        for value in [float('nan'),float('inf'),-float('inf'),'NaN','1e999']:
            with self.subTest(value=value):
                f,c = self.compare({'profit':value})
                self.assertEqual(c['status'],'failed')
    def test_invalid_missing_values_not_passed(self):
        for value in [None,True,'','100%','unknown']:
            with self.subTest(value=value):
                f,c = self.compare({'profit':value})
                self.assertNotEqual(c['status'],'passed')
    def test_missing_code_results_reported(self):
        c={}; f=audit.compare_results(self.registry,[],1e-8,c)
        self.assertEqual(c['status'],'not_checked')
        self.assertTrue(f)
    def test_duplicate_json_key_blocked(self):
        f,c = self.compare('{"profit":100,"profit":100}')
        self.assertEqual(c['status'],'failed')
    def test_duplicate_result_id_blocked(self):
        rows=[{'result_id':'q1','value':100}]*2
        f,c=self.compare(rows,rows[:1])
        self.assertEqual(c['status'],'failed')
    def test_duplicate_csv_header_blocked(self):
        f,c=self.compare('profit,profit\n100,100\n',suffix='.csv')
        self.assertEqual(c['status'],'failed')
    def test_multiline_csv_requires_identity(self):
        f,c=self.compare('profit\n100\n200\n',suffix='.csv')
        self.assertEqual(c['status'],'failed')
    def test_unit_and_version_mismatch(self):
        for meta in ['unit','version','run_id']:
            with self.subTest(meta=meta):
                f,c=self.compare({'result_id':'q1','value':100,meta:'new'}, {'result_id':'q1','value':100,meta:'old'})
                self.assertEqual(c['status'],'failed')
    def test_metadata_missing_reported(self):
        f,c=self.compare({'result_id':'q1','value':100}, {'result_id':'q1','value':100,'unit':'kg'})
        self.assertEqual(c['status'],'partial')
    def test_partial_file_coverage(self):
        f,c=self.compare({'profit':100}, {'profit':100,'cost':50})
        self.assertEqual(c['status'],'partial')
        self.assertEqual(len(c['unmatched_registry']),1)
    def test_multiple_files_complete_coverage(self):
        self.registry.write_text('{"profit":100,"cost":50}',encoding='utf-8')
        p1=self.root/'a.json';p2=self.root/'b.json'
        p1.write_text('{"profit":100}',encoding='utf-8');p2.write_text('{"cost":50}',encoding='utf-8')
        c={}; f=audit.compare_results(self.registry,[p1,p2],1e-8,c)
        self.assertEqual(f,[]);self.assertEqual(c['matched_fields'],2)
    def test_duplicate_output_files_blocked(self):
        p=self.root/'a.json';p.write_text('{"profit":100}',encoding='utf-8')
        c={}; f=audit.compare_results(self.registry,[p,p],1e-8,c)
        self.assertEqual(c['status'],'failed')
    def test_invalid_tolerance_rejected(self):
        for value in [-1,float('nan'),float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.compare_results(self.registry,[],value)
    def test_failed_output_status_blocked(self):
        f,c=self.compare({'profit':100,'status':'failed'})
        self.assertEqual(c['status'],'failed')
    def test_pending_registry_not_passed(self):
        f,c=self.compare({'profit':100}, {'profit':100,'status':'pending'})
        self.assertEqual(c['status'],'partial')
    def test_verified_registry_success_output(self):
        f,c=self.compare({'profit':100,'status':'success'}, {'profit':100,'status':'verified'})
        self.assertEqual(f,[])
    def test_cli_exit_codes_and_json(self):
        for value,expected in [(100,0),(999,2)]:
            output=self.root/'output.csv'; output.write_text(f'profit\n{value}\n',encoding='utf-8')
            report=self.root/'report.json'
            proc=subprocess.run([sys.executable,'-X','utf8',str(HERE/'audit_paper_integrity.py'),'--result-registry',str(self.registry),'--code-result',str(output),'--json-output',str(report)],capture_output=True,encoding='utf-8')
            self.assertEqual(proc.returncode,expected,proc.stderr)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['numeric_coverage']['matched_fields'],1)
        proc=subprocess.run([sys.executable,'-X','utf8',str(HERE/'audit_paper_integrity.py'),'--result-registry',str(self.registry)],capture_output=True,encoding='utf-8')
        self.assertEqual(proc.returncode,1)

class CaptionTests(unittest.TestCase):
    def test_prose_is_not_duplicate_caption(self):
        self.assertEqual(audit.check_caption_sequence(['图1 预测误差分布','图1表明误差集中。','图1 表明误差集中。']),[])
    def test_out_of_order_detected(self):
        findings=audit.check_caption_sequence(['图2 结果分布','图1 误差分布'])
        self.assertTrue(any('顺序错误' in f.evidence for f in findings))
    def test_ambiguous_title_not_blocker(self):
        findings=audit.check_caption_sequence(['图1预测误差分布'])
        self.assertTrue(findings)
        self.assertFalse(any(f.severity=='blocker' for f in findings))
    def test_explicit_word_caption_duplicates_blocked(self):
        with tempfile.TemporaryDirectory(prefix='agent_docx_') as temp:
            path=Path(temp)/'paper.docx'
            xml=f'''<w:document xmlns:w="{audit.W_NS}"><w:body><w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>图1误差</w:t></w:r></w:p><w:p><w:r><w:t>图1表明误差集中。</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>图1结果</w:t></w:r></w:p></w:body></w:document>'''
            with zipfile.ZipFile(path,'w') as archive: archive.writestr('word/document.xml',xml)
            data=audit.read_docx(path)
            self.assertEqual(len(data.caption_paragraphs),2)
            self.assertTrue(any(f.severity=='blocker' for f in audit.check_caption_sequence(data.paragraphs,data.caption_paragraphs)))

@unittest.skipUnless(os.name=='nt','PowerShell synchronization tests run on Windows')
class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='agent_sync_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source'
        for name in SKILLS+['scripts','shared-references']:
            (self.source/name).mkdir(parents=True)
        (self.source/'AGENTS.md').write_text('fixture marker',encoding='utf-8')
        (self.source/'paper-review/scripts').mkdir()
        validator=self.source/'paper-review/scripts/validate_skill_suite.py'
        validator.write_text("import sys\nfrom pathlib import Path\nr=Path(sys.argv[1])\nraise SystemExit(1 if (r/'fail-installed').exists() and r.name=='installed' else 0)\n",encoding='utf-8')
        self.script=self.source/'scripts/sync_workbuddy_skills.ps1'
        shutil.copy2(HERE.parents[1]/'scripts/sync_workbuddy_skills.ps1',self.script)
        self.target=self.root/'installed'
        self.ps=shutil.which('pwsh') or shutil.which('powershell')
    def run_sync(self,target=None,extra=()):
        return subprocess.run([self.ps,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(self.script),'-TargetSkillRoot',str(target or self.target),'-Python',sys.executable,*extra],capture_output=True,encoding='utf-8',errors='replace')
    def test_disjoint_new_install(self):
        p=self.run_sync();self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue((self.target/'AGENTS.md').is_file())
    def test_equal_ancestor_descendant_rejected(self):
        for target in [self.source,self.root,self.source/'child']:
            with self.subTest(target=target):
                p=self.run_sync(target);self.assertNotEqual(p.returncode,0)
                self.assertTrue(self.script.exists())
        self.assertFalse((self.source/'child').exists())
    def test_unmanaged_directory_untouched(self):
        self.target.mkdir();sentinel=self.target/'personal.txt';sentinel.write_text('keep',encoding='utf-8')
        p=self.run_sync();self.assertNotEqual(p.returncode,0)
        self.assertEqual(sentinel.read_text(encoding='utf-8'),'keep')
    def test_whatif_does_not_mutate(self):
        p=self.run_sync(extra=['-WhatIf']);self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(sorted(x.name for x in self.root.iterdir()),['source'])
    def test_existing_install_has_backup(self):
        shutil.copytree(self.source,self.target)
        (self.target/'modeling-design/old.txt').write_text('old',encoding='utf-8')
        p=self.run_sync();self.assertEqual(p.returncode,0,p.stderr)
        backups=list(self.root.glob('.installed.backup_*'));self.assertEqual(len(backups),1)
        self.assertEqual((backups[0]/'modeling-design/old.txt').read_text(encoding='utf-8'),'old')
    def test_validation_failure_restores_old_target(self):
        shutil.copytree(self.source,self.target)
        (self.target/'modeling-design/old.txt').write_text('old',encoding='utf-8')
        (self.source/'fail-installed').write_text('fixture',encoding='utf-8')
        p=self.run_sync();self.assertNotEqual(p.returncode,0)
        self.assertEqual((self.target/'modeling-design/old.txt').read_text(encoding='utf-8'),'old')
        self.assertFalse((self.target/'fail-installed').exists())
    def test_move_failure_restores_backup(self):
        shutil.copytree(self.source,self.target)
        (self.target/'modeling-design/old.txt').write_text('old',encoding='utf-8')
        wrapper=self.root/'inject_move_failure.ps1'
        wrapper.write_text("""param($ScriptPath,$TargetPath,$PythonPath)
function Move-Item {
    [CmdletBinding()] param([string]$LiteralPath,[string]$Destination)
    if ($Destination -eq $TargetPath -and $LiteralPath -like '*.candidate_*') { throw 'simulated installation move failure' }
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination -ErrorAction Stop
}
& $ScriptPath -TargetSkillRoot $TargetPath -Python $PythonPath
""",encoding='utf-8')
        p=subprocess.run([self.ps,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(wrapper),str(self.script),str(self.target),sys.executable],capture_output=True,encoding='utf-8',errors='replace')
        self.assertNotEqual(p.returncode,0)
        self.assertEqual((self.target/'modeling-design/old.txt').read_text(encoding='utf-8'),'old')
        self.assertEqual(list(self.root.glob('.installed.backup_*')),[])
    def test_linked_target_parent_rejected(self):
        destination=self.root/'outside';destination.mkdir()
        link=self.root/'junction'
        runner=self.root/'junction.ps1'
        runner.write_text("param($LinkPath,$DestinationPath)\nNew-Item -ItemType Junction -Path $LinkPath -Target $DestinationPath -ErrorAction Stop | Out-Null\n",encoding='utf-8')
        proc=subprocess.run([self.ps,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(runner),str(link),str(destination)],capture_output=True,encoding='utf-8',errors='replace')
        self.assertEqual(proc.returncode,0,proc.stderr)
        p=self.run_sync(link/'installed')
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((destination/'installed').exists())
    def test_new_install_failure_leaves_no_target(self):
        (self.source/'fail-installed').write_text('fixture',encoding='utf-8')
        p=self.run_sync();self.assertNotEqual(p.returncode,0)
        self.assertFalse(self.target.exists())
        self.assertEqual(len(list(self.root.glob('.installed.failed_*'))),1)
    def test_candidate_failure_leaves_target_untouched(self):
        shutil.copytree(self.source,self.target)
        (self.target/'modeling-design/old.txt').write_text('old',encoding='utf-8')
        (self.source/'paper-review/scripts/validate_skill_suite.py').write_text('raise SystemExit(1)',encoding='utf-8')
        p=self.run_sync();self.assertNotEqual(p.returncode,0)
        self.assertEqual((self.target/'modeling-design/old.txt').read_text(encoding='utf-8'),'old')
        self.assertEqual(list(self.root.glob('.installed.backup_*')),[])

if __name__=='__main__':
    unittest.main(verbosity=2)
