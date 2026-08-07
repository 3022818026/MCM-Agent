#!/usr/bin/env python3
"""Static validation for the project mathematics-modeling skill suite."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SKILLS = [
    "modeling-scientist",
    "modeling-design",
    "data-preparation",
    "model-implementation",
    "model-evaluation",
    "figure-generation",
    "paper-writing",
    "paper-review",
]
REQUIRED_SKILL_GATE_PHRASE = "全程质量闭环"
PERSISTENT_BASELINE = [
    "agent_runtime_protocol.md",
    "artifact_build_release_protocol.md",
    "rule_authority_index.md",
    "quality_gate_protocol.md",
    "user_delivery_contract.md",
]
PAPER_WRITING_REQUIRED_REFS = [
    "common_writing_requirements.md",
    "paper_integrity_gate.md",
    "academic_style_revision.md",
    "evidence_claim_discipline.md",
    "word_formula_output_protocol.md",
]
PAPER_REVIEW_REQUIRED_REFS = [
    "paper_integrity_gate.md",
    "evaluator_review_principles.md",
    "academic_style_revision.md",
    "evidence_claim_discipline.md",
]
ACADEMIC_STYLE_AUTHORITY_PHRASE = "论文正文语言与语义规范的最高权威"

REQUIRED_SECTION_GROUPS = [
    ("任务目标",),
    ("开始前读取", "开始前读取内容", "读取范围与证据边界"),
    ("执行步骤", "执行流程"),
    ("输出", "输出格式", "输出契约"),
    ("禁止", "禁止事项"),
    ("完成标准",),
]
FORBIDDEN_DEFAULTS = [
    r"(?m)^\s*(?:[-*]\s*)?默认使用\s*XGBoost",
    r"(?m)^\s*(?:[-*]\s*)?默认使用\s*Huber",
    r"(?m)^\s*(?:[-*]\s*)?默认采用\s*五折",
    r"(?m)^\s*(?:[-*]\s*)?默认使用\s*80%.*20%",
    r"综合评分最高[^。\n]*必然最佳",
    r"测试集.*调参是允许的",
    r"(?m)^\s*(?:[-*]\s*)?时间序列(?:数据)?(?:默认|应|可以)[^\n]*随机划分",
    r"(?i)compare exactly three routes|必须比较恰好三(?:条|种)路线|固定三(?:条|种)路线",
    r"(?i)default to at least two figures|每(?:个|一)问至少(?:生成|绘制|包含)?\s*2\s*张图",
    r"完整论文必须是\s*TeX|最终论文(?:必须|只能).*TeX",
    r"(?:所有|全部)(?:数值|结果).*最多保留\s*2\s*位小数",
    r"默认(?:使用|采用)\s*Jet(?:色图|配色|colormap)?",
    r"(?:所有|全部)图(?:表|像)?[^\n]*(?:统一|固定)[^\n]*18\s*(?:号|pt)",
    r"(?m)^\s*(?:[-*]\s*)?(?!不|不得|禁止)(?:所有|全部)图(?:表|像)?[^\n]*(?:固定|默认)[^\n]*2\s*[×xX]\s*2",
]

REQUIRED_GUARDRAILS = {
    \
    "shared-references/competition_workflow.md": ["短指令意图补全与应急模式", "覆盖范围", "质量标准"],
    "shared-references/common_modeling_principles.md": ["题面结构解析与混合题型", "自动拆题结果都只是候选解析", "关键措辞台账", "题面措辞→数学对象"],
    "shared-references/common_code_requirements.md": ["模型—代码反向核对", "原始字段到代码变量", "跨平台调用方式", "MATLAB分析与Python绘图协议", "main.m", "rng", "paper_plot_library.py"],
    "shared-references/evaluator_review_principles.md": ["正确性证据阶梯", "独立交叉核验", "压力/边界/失效测试", "自动检查的证据边界", "自动检查通过只能表示", "独立复算代表性数值"],
    "shared-references/evidence_claim_discipline.md": ["证据分级与可支持范围", "模型记忆", "主张链", "引用与检索的能力降级", "AI 协作与人工确认边界"],
    "shared-references/quality_gate_protocol.md": ["问题分级", "需要用户确认", "早停与回退", "反向审视与独立性", "交付问题台账", "全程生成—审查—修复闭环", "生成前门禁", "生成后审查", "未通过时的修复闭环", "责任路由"],
    "shared-references/paper_integrity_gate.md": ["关键措辞台账", "论文有而代码无"],
    "shared-references/model_comparison_decision_rules.md": ["候选方法卡", "不适用条件", "常见失败信号"],
    "shared-references/artifact_build_release_protocol.md": ["能力—替代矩阵", "不得硬依赖单一生态", "文档—实现脱节"],
    "shared-references/common_figure_requirements.md": ["Python论文制图与去模板化风格", "12—18 pt之间调整", "深色、高饱和度、高对比度", "三维饼图和三维柱状图可以采用", "常见AI模板痕迹"],
    "paper-writing/references/competition_prose_style.md": ["逻辑先行，叙述自然", "准确、克制、有边界", "分节叙述契约", "去模板化与润色检查", "交付前自检"],
    "shared-references/user_delivery_contract.md": ["默认使用MATLAB", "MATLAB R2023b", "未经用户明确同意", "12—18 pt之间调整", "三维饼图和三维柱状图不是禁用项"],
    "shared-references/rule_authority_index.md": ["常驻基线", "规则权威来源", "按需加载矩阵", "不得无任务地批量加载全部历史文件"],
}


def _extract_agents_persistent_baseline(content: str) -> list[str] | None:
    marker = "还必须完整读取："
    if marker not in content:
        return None
    bullet_block = content.split(marker, 1)[1].lstrip().split("\n\n", 1)[0]
    files = re.findall(r"`(?:\.agents/skills/)?(?:shared-references/)?([^`/]+\.md)`", bullet_block)
    return files or None


def _extract_index_persistent_baseline(content: str) -> list[str] | None:
    line = next((item for item in content.splitlines() if "任何数学建模Skill均完整读取：" in item), None)
    if line is None:
        return None
    baseline_clause = line.split("。", 1)[0]
    files = re.findall(r"`([^`]+\.md)`", baseline_clause)
    return files or None


def _validate_persistent_baseline(root: Path, failures: list[str]) -> int:
    index_path = root / "shared-references" / "rule_authority_index.md"
    agent_paths = [root / "AGENTS.md"]
    workspace_agents = root.parent.parent / "AGENTS.md"
    if workspace_agents.exists() and workspace_agents not in agent_paths:
        agent_paths.insert(0, workspace_agents)

    index_files = _extract_index_persistent_baseline(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
    if index_files != PERSISTENT_BASELINE:
        failures.append(
            "shared-references/rule_authority_index.md: persistent baseline must be "
            f"{PERSISTENT_BASELINE}; found {index_files}"
        )

    for agents_path in agent_paths:
        agents_files = _extract_agents_persistent_baseline(agents_path.read_text(encoding="utf-8")) if agents_path.exists() else None
        label = agents_path.as_posix()
        if agents_files != PERSISTENT_BASELINE:
            failures.append(f"{label}: persistent baseline must be {PERSISTENT_BASELINE}; found {agents_files}")
        if agents_files != index_files:
            failures.append(f"persistent baseline mismatch: {label}={agents_files}; rule_authority_index.md={index_files}")
    return 1 + 2 * len(agent_paths)
def _validate_paper_writing_reference_contract(root: Path, failures: list[str]) -> int:
    skill_path = root / "paper-writing" / "SKILL.md"
    index_path = root / "shared-references" / "rule_authority_index.md"
    skill_content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    index_content = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    row = re.search(r"(?m)^\|\s*`paper-writing`\s*\|([^|]*)\|", index_content)
    checks = 0

    for reference in PAPER_WRITING_REQUIRED_REFS:
        checks += 1
        if reference not in skill_content:
            failures.append(f"paper-writing/SKILL.md: missing required writing reference: {reference}")
    checks += 1
    if ACADEMIC_STYLE_AUTHORITY_PHRASE not in skill_content:
        failures.append("paper-writing/SKILL.md: academic_style_revision.md is not declared as the language-and-semantics authority")

    checks += 1
    if row is None:
        failures.append("shared-references/rule_authority_index.md: missing paper-writing matrix row")
    else:
        specialist_reads = row.group(1)
        for reference in PAPER_WRITING_REQUIRED_REFS:
            checks += 1
            if reference not in specialist_reads:
                failures.append(
                    "shared-references/rule_authority_index.md: paper-writing "
                    f"specialist reads missing {reference}"
                )
    return checks


def _validate_paper_review_reference_contract(root: Path, failures: list[str]) -> int:
    skill_path = root / "paper-review" / "SKILL.md"
    index_path = root / "shared-references" / "rule_authority_index.md"
    skill_content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    index_content = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    row = re.search(r"(?m)^\|\s*`paper-review`\s*\|([^|]*)\|", index_content)
    checks = 0

    for reference in PAPER_REVIEW_REQUIRED_REFS:
        checks += 1
        if reference not in skill_content:
            failures.append(f"paper-review/SKILL.md: missing required review reference: {reference}")

    checks += 1
    if row is None:
        failures.append("shared-references/rule_authority_index.md: missing paper-review matrix row")
    else:
        specialist_reads = row.group(1)
        for reference in PAPER_REVIEW_REQUIRED_REFS:
            checks += 1
            if reference not in specialist_reads:
                failures.append(
                    "shared-references/rule_authority_index.md: paper-review "
                    f"specialist reads missing {reference}"
                )
    return checks

def validate(root: Path) -> dict:
    failures: list[str] = []
    checks = 0
    checks += _validate_persistent_baseline(root, failures)
    checks += _validate_paper_writing_reference_contract(root, failures)
    checks += _validate_paper_review_reference_contract(root, failures)
    for name in SKILLS:
        skill_dir = root / name
        skill_file = skill_dir / "SKILL.md"
        meta_file = skill_dir / "agents" / "openai.yaml"
        if not skill_file.exists():
            failures.append(f"{name}: missing SKILL.md")
            continue
        content = skill_file.read_text(encoding="utf-8")
        checks += 1
        match = re.match(r"^---\n(.*?)\n---\n", content, re.S)
        if not match:
            failures.append(f"{name}: invalid frontmatter")
        else:
            front = match.group(1)
            keys = re.findall(r"^([a-z_]+):", front, re.M)
            if keys != ["name", "description"]:
                failures.append(f"{name}: frontmatter keys are {keys}")
            if f"name: {name}" not in front:
                failures.append(f"{name}: name mismatch")
        for alternatives in REQUIRED_SECTION_GROUPS:
            checks += 1
            if not any(
                re.search(
                    rf"^##\s+(?:\d+\.\s*)?{re.escape(section)}(?:\s|$)",
                    content,
                    re.M,
                )
                for section in alternatives
            ):
                failures.append(
                    f"{name}: missing section group "
                    f"{'/'.join(alternatives)}"
                )
        checks += 1
        if re.search(r"(?im)^\s*(?:[-*]\s*)?TODO\s*(?::|：|$)", content):
            failures.append(f"{name}: contains unresolved TODO marker")
        checks += 1
        if not meta_file.exists():
            failures.append(f"{name}: missing agents/openai.yaml")
        checks += 1
        if "rule_authority_index.md" not in content:
            failures.append(f"{name}: missing rule-authority index reference")
        checks += 1
        if REQUIRED_SKILL_GATE_PHRASE not in content:
            failures.append(f"{name}: missing common quality-closure hook")

    corpus = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.md"))
    for pattern in FORBIDDEN_DEFAULTS:
        checks += 1
        if re.search(pattern, corpus, re.I | re.S):
            failures.append(f"forbidden default matched: {pattern}")

    for relative_path, phrases in REQUIRED_GUARDRAILS.items():
        path = root / relative_path
        checks += 1
        if not path.exists():
            failures.append(f"missing guardrail file: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        for phrase in phrases:
            checks += 1
            if phrase not in content:
                failures.append(f"{relative_path}: missing guardrail phrase: {phrase}")

    required_refs = {
        "codex_project_context_rules.md",
        "historical_memory_usage_rules.md",
        "common_modeling_principles.md",
        "model_comparison_decision_rules.md",
        "model_selection_and_evaluation.md",
        "paper_model_comparison_writing.md",
        "common_writing_requirements.md",
        "common_figure_requirements.md",
        "common_code_requirements.md",
        "common_mistakes.md",
        "historical_case_lessons.md",
        "user_delivery_contract.md",
        "project_learning_loop.md",
        "competition_workflow.md",
        "paper_integrity_gate.md",
        "academic_style_revision.md",
        "evaluator_review_principles.md",
        "evidence_claim_discipline.md",
        "quality_gate_protocol.md",
        "agent_runtime_protocol.md",
        "artifact_build_release_protocol.md",
        "rule_authority_index.md",
    }
    existing = {p.name for p in (root / "shared-references").glob("*.md")}
    checks += len(required_refs)
    for missing in sorted(required_refs - existing):
        failures.append(f"missing shared reference: {missing}")

    return {"status": "pass" if not failures else "fail", "checks": checks, "skills": len(SKILLS), "shared_references": len(existing), "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(args.skill_root.resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} checks={result['checks']}")
        for failure in result["failures"]:
            print(f"- {failure}")
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()







