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
    "paper_writing_revision_contract.md",
]
PAPER_WRITING_REQUIRED_REFS = [
    "paper_writing_revision_contract.md",
    "common_writing_requirements.md",
    "paper_integrity_gate.md",
    "academic_style_revision.md",
    "evidence_claim_discipline.md",
    "word_formula_output_protocol.md",
    "paper_model_comparison_writing.md",
]
PAPER_REVIEW_REQUIRED_REFS = [
    "paper_writing_revision_contract.md",
    "paper_integrity_gate.md",
    "evaluator_review_principles.md",
    "academic_style_revision.md",
    "evidence_claim_discipline.md",
    "supervisor_review_lens.md",
    "paper_model_comparison_writing.md",
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
    "shared-references/common_modeling_principles.md": ["题目结果总目标门禁", "题目原句—必须回答的判断/数值/方案", "关键数值可复算", "题面结构解析与混合题型", "自动拆题结果都只是候选解析", "关键措辞台账", "题面措辞→数学对象", "统一基础评价器", "跨阶段模型接口", "继承项—新增项—替换项—失效项"],
    "data-preparation/SKILL.md": ["数据处理决策台账", "清洁基础数据", "模型就绪", "数据清单", "下游数据消费契约", "箱线图", "不得对全量数据先拟合处理器再划分"],
    "shared-references/common_code_requirements.md": ["锁定数据版本与单一来源", "数据清单", "不得再次临时删除", "模型—代码反向核对", "原始字段到代码变量", "跨平台调用方式", "统一评价器与模型接口实现", "重复计量测试", "机器可读接口表", "MATLAB分析与Python绘图协议", "main.m", "rng", "paper_plot_library.py"],
    "modeling-scientist/SKILL.md": ["经确认的内部机器学习核验", "取得明确确认后再训练", "不因“不写论文”而降低复现与证据标准"],
    "modeling-design/SKILL.md": ["内部核验卡", "未确认前只保留为候选计划"],
    "shared-references/evaluator_review_principles.md": ["正确性证据阶梯", "独立交叉核验", "压力/边界/失效测试", "验证职责分离与模型晋级", "同一证据族", "反演/参数估计", "统计到决策链", "自动检查的证据边界", "自动检查通过只能表示", "独立复算代表性数值"],
    "shared-references/evidence_claim_discipline.md": ["证据分级与可支持范围", "模型记忆", "主张链", "引用与检索的能力降级", "国家或行业标准", "DOI或官方链接", "来源之间冲突", "外部资料是辅助验证证据", "AI 协作与人工确认边界"],
    "shared-references/quality_gate_protocol.md": ["Skill执行握手", "活动规则卡", "问题分级", "需要用户确认", "早停与回退", "反向审视与独立性", "交付问题台账", "全程生成—审查—修复闭环", "生成前门禁", "生成后审查", "未通过时的修复闭环", "责任路由"],
    "shared-references/paper_integrity_gate.md": ["关键措辞台账", "论文有而代码无", "问题背景", "每个独立公式是否有唯一公式号", "保真润色", "反向核对", "摘要是否通过独立可读性检查", "占位符语义", "不允许读者猜测“—”"],
    "shared-references/model_comparison_decision_rules.md": ["候选方法卡", "不适用条件", "常见失败信号"],
    "shared-references/artifact_build_release_protocol.md": ["能力—替代矩阵", "不得硬依赖单一生态", "文档—实现脱节"],
    "shared-references/common_figure_requirements.md": ["数据质量诊断图", "锁定的清洁基础数据", "Python论文制图与去模板化风格", "12—18 pt之间调整", "克制的深色高对比度", "3D图只在数据确含第三维", "数据最稀疏", "常见AI模板痕迹"],
    "figure-generation/references/chart_selection_and_flowchart_style.md": ["常用图形与初始比例", "图例放在", "流程图强制风格", "3列蛇形布局"],
    "paper-writing/references/competition_prose_style.md": ["逻辑先行，叙述自然", "准确、克制、有边界", "分节叙述契约", "写前段落契约与证据骨架", "主张—证据—解释—边界/承接", "去模板化与润色检查", "交付前自检"],
    "paper-writing/references/word_formula_output_protocol.md": ["每个独立居中公式还必须具有公式号", "正文引用统一写为", "不得以空格手工推齐", "编号错位"],
    "shared-references/paper_writing_revision_contract.md": [
        "常驻高优先级用户合同",
        "每次调用的跨阶段强制动作",
        "背景+问题+解决方法+意义+针对每个问题的重要结论",
        "约100字",
        "每个实际问题单独一段",
        "数据来源或选取范围",
        "不得纯罗列全部指标",
        "长短句结合",
        "实际不便",
        "现实意义",
        "每个问题的具体要求与措施单独一段",
        "因素考虑和数据处理",
        "真实案例或文献",
        "AI式假设清单",
        "标题优先展示",
        "不了解该模型的读者",
        "公式说明来历和作用",
        "优先采用可复现的数值积分",
        "评价使用准确、易懂",
        "不在模型评价中重复结果部分",
        "附件写作合同审查",
        "不能用抽样段落代替全文检查",
    ],
    "shared-references/user_delivery_contract.md": ["严谨、准确地解决题目", "锁定数据版本", "下游临时清洗", "机器学习仅用于内部核对", "不得隐瞒会推翻或削弱", "允许检索真实可信的文献", "外部资料不得替代题面", "默认使用MATLAB", "MATLAB R2023b", "未经用户明确同意", "12—18 pt之间调整", "候选模型比较与正文边界", "纯装饰3D不使用", "问题一分析", "每个独立居中公式必须带公式号", "不得直接交付未经润色的初稿", "仅看摘要即可明白全文", "Markdown加粗", "表中结果不得莫名其妙写成“—”"],
    "shared-references/common_writing_requirements.md": ["候选模型比较与正文边界", "不自动进入论文正文", "最终采用的模型", "仅看摘要就应能明白", "结果解释闭环", "同一张表不得让“—”兼指多个原因"],
    "shared-references/paper_model_comparison_writing.md": ["内部比较", "机器学习可以只作为内部核验模型", "不得隐去会推翻、显著削弱或改变", "正文默认写法", "例外披露", "措辞边界"],
    "shared-references/supervisor_review_lens.md": ["定位与权威边界", "终审前置：提交画像与覆盖声明", "主张—模块—证据反向映射", "分节角色复核", "发现质量、严重度与提交结论", "条件触发的外部检索与语言检查", "不可直接迁移的外部约束", "固定三至五天审稿时点", "不为任何结论提供证据"],
    "paper-review/SKILL.md": ["提交画像与覆盖矩阵", "精确证据位置", "全文机械扫描不得以抽样代替", "最优先三项修复", "最终提交结论必须与未关闭问题一致", "摘要独立可读性", "结果解释闭环", "表格占位符语义"],
    "shared-references/academic_style_revision.md": ["语义风险分级", "强制后置润色闭环", "反向逐项核对", "只交付通过润色门禁"],
    "paper-writing/SKILL.md": ["生成后强制润色", "不得直接交付初稿", "反向逐项核对", "摘要独立可读性检查", "Markdown加粗", "表格中的“—”必须在表注中定义唯一含义"],
    "shared-references/rule_authority_index.md": ["常驻基线", "规则权威来源", "按需加载矩阵", "不得无任务地批量加载全部历史文件", "初稿不得绕过后置润色直接交付"],
    "paper-review/scripts/audit_paper_integrity.py": ["check_table_dash_cells", "表格占位符语义", "保留破折号时在该表表注中定义唯一含义"],
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

def _validate_stage_chain(root: Path, failures: list[str]) -> int:
    """Check stage identity and dependency links, including copied skill suites."""
    chain = root / "shared-references" / "MATH_MODELING_AGENT_PROMPT_CHAIN.md"
    checks = 1
    if not chain.is_file():
        failures.append("missing canonical thirteen-stage chain")
        return checks
    text = chain.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^## 阶段 (\d+)：([^\n]+)", text))
    checks += 1
    if [int(m.group(1)) for m in matches] != list(range(1, 14)):
        failures.append("canonical stage IDs must occur exactly once in order 1..13")
    for i, match in enumerate(matches):
        section = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        for field in ("**调用 Skills：**", "**交接物：**", "**放行条件：**"):
            checks += 1
            if field not in section:
                failures.append(f"stage {match.group(1)} missing {field}")
        line = next((line for line in section.splitlines() if line.startswith("**调用 Skills：**")), "")
        for skill in re.findall(r"`([a-z]+(?:-[a-z]+)+)`", line):
            checks += 1
            if skill not in SKILLS or not (root / skill / "SKILL.md").is_file():
                failures.append(f"stage {match.group(1)} references unavailable skill {skill}")
    entrypoints = [root / "shared-references" / "competition_workflow.md"]
    workspace = root.parent.parent
    if (workspace / "MODELING_AGENT_EXECUTION_PROTOCOL.md").is_file():
        entrypoints.extend(workspace / name for name in ("AGENTS.md", "MODELING_AGENT_EXECUTION_PROTOCOL.md", "MATH_MODELING_AGENT_PROMPT_CHAIN.md"))
    for path in entrypoints:
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        checks += 1
        if "MATH_MODELING_AGENT_PROMPT_CHAIN.md" not in content:
            failures.append(f"missing chain reference: {path}")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]*)?\)", content):
            if "://" not in target:
                checks += 1
                if not (path.parent / target).resolve().is_file():
                    failures.append(f"broken markdown link: {path}: {target}")
    for path in root.rglob("*.md"):
        checks += 1
        content = path.read_text(encoding="utf-8")
        if re.search(r"(?m)^#+[^\n]*(?:九阶段|9阶段)", content):
            failures.append(f"obsolete stage sequence: {path}")
        if path != chain and re.search(r"(?m)^## 阶段 \d+：", content):
            failures.append(f"duplicate numbered stage definition: {path}")
    return checks


def validate(root: Path) -> dict:
    failures: list[str] = []
    checks = 0
    checks += _validate_stage_chain(root, failures)
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
        if "paper_writing_revision_contract.md" not in content:
            failures.append(f"{name}: missing persistent paper-writing revision contract reference")
        checks += 1
        if REQUIRED_SKILL_GATE_PHRASE not in content:
            failures.append(f"{name}: missing common quality-closure hook")
        checks += 1
        if "Skill执行握手" not in content:
            failures.append(f"{name}: missing mandatory skill-execution handshake")

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
        "MATH_MODELING_AGENT_PROMPT_CHAIN.md",
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
        "paper_writing_revision_contract.md",
        "supervisor_review_lens.md",
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







