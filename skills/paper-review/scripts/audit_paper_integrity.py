#!/usr/bin/env python3
"""对数学建模论文执行可复现的完整性初筛。

自动检查只能定位候选问题，不能替代人工核查模型机理、结论边界和版式。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"

PLACEHOLDERS = (
    "此处插入", "下一部分", "latex代码", "todo",
    "待补充", "待修改", "请在此", "占位",
)
IDENTITY_KEYS = ("作者", "姓名", "学校", "学院", "学号", "指导教师", "邮箱", "手机")
SYMBOL_PATTERN = re.compile(r"(?<![A-Za-z])(?:[A-Za-z]|[α-ωΑ-Ω])(?:_[A-Za-z0-9]+)?")
NUMBER_PATTERN = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?%?(?![\w.])")
CITATION_PATTERN = re.compile(r"\[(\d{1,3})\]")
CAPTION_PATTERN = re.compile(r"^\s*(图|表)\s*(\d+)")


@dataclass
class Finding:
    severity: str
    check: str
    evidence: str
    action: str


@dataclass
class DocumentData:
    paragraphs: list[str]
    tables: list[list[list[str]]]
    formulas: list[str]
    metadata: dict[str, str]

    @property
    def text(self) -> str:
        table_text = "\n".join(
            "\t".join(cell for cell in row) for table in self.tables for row in table
        )
        return "\n".join(self.paragraphs + ([table_text] if table_text else []))


def _texts(node: ET.Element, namespace: str) -> str:
    return "".join(item.text or "" for item in node.iter(f"{{{namespace}}}t")).strip()


def read_docx(path: Path) -> DocumentData:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = [_texts(p, W_NS) for p in document.iter(f"{{{W_NS}}}p")]
        paragraphs = [text for text in paragraphs if text]
        tables: list[list[list[str]]] = []
        for table in document.iter(f"{{{W_NS}}}tbl"):
            rows: list[list[str]] = []
            for row in table.iter(f"{{{W_NS}}}tr"):
                cells = [_texts(cell, W_NS) for cell in row.iter(f"{{{W_NS}}}tc")]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        formulas = [
            _texts(formula, M_NS)
            for formula in document.iter(f"{{{M_NS}}}oMath")
            if _texts(formula, M_NS)
        ]
        metadata: dict[str, str] = {}
        if "docProps/core.xml" in archive.namelist():
            core = ET.fromstring(archive.read("docProps/core.xml"))
            tags = {
                "creator": f"{{{DC_NS}}}creator",
                "lastModifiedBy": f"{{{CP_NS}}}lastModifiedBy",
                "title": f"{{{DC_NS}}}title",
            }
            for label, tag in tags.items():
                node = core.find(tag)
                if node is not None and node.text:
                    metadata[label] = node.text.strip()
    return DocumentData(paragraphs, tables, formulas, metadata)


def read_pdf(path: Path) -> tuple[str, int, dict[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("检查 PDF 需安装 pypdf：pip install pypdf") from exc
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    metadata = {
        str(key): str(value)
        for key, value in (reader.metadata or {}).items()
        if value
    }
    return text, len(reader.pages), metadata


def check_placeholders(text: str) -> list[Finding]:
    lowered = text.lower()
    return [
        Finding("blocker", "占位内容", token, "删除占位内容并补入最终正文或图表。")
        for token in PLACEHOLDERS if token in lowered
    ]


def check_citations(text: str) -> list[Finding]:
    match = re.search(r"(参考文献|References)", text, re.I)
    if not match:
        return [Finding("warning", "参考文献", "未识别到参考文献标题", "人工确认参考文献章节。")]
    body, references = text[:match.start()], text[match.end():]
    cited = {int(value) for value in CITATION_PATTERN.findall(body)}
    listed = {int(value) for value in re.findall(r"(?m)^\s*\[(\d{1,3})\]", references)}
    findings = [
        Finding("blocker", "引用双向对应", f"正文引用[{value}]未列入参考文献", "补充条目或删除引用。")
        for value in sorted(cited - listed)
    ]
    findings += [
        Finding("warning", "引用双向对应", f"参考文献[{value}]未在正文引用", "补充正文引用或删除条目。")
        for value in sorted(listed - cited)
    ]
    return findings


def check_caption_sequence(paragraphs: Iterable[str]) -> list[Finding]:
    sequences: dict[str, list[int]] = {"图": [], "表": []}
    for paragraph in paragraphs:
        match = CAPTION_PATTERN.match(paragraph)
        if match:
            sequences[match.group(1)].append(int(match.group(2)))
    findings: list[Finding] = []
    for kind, values in sequences.items():
        if not values:
            continue
        duplicates = sorted({value for value in values if values.count(value) > 1})
        missing = sorted(set(range(1, max(values) + 1)) - set(values))
        if duplicates:
            findings.append(Finding("blocker", f"{kind}编号", f"重复编号：{duplicates}", "按正文顺序重新编号。"))
        if missing:
            findings.append(Finding("warning", f"{kind}编号", f"缺失编号：{missing}", "确认是否漏项或编号错误。"))
    return findings


def check_symbol_candidates(data: DocumentData) -> list[Finding]:
    if not data.formulas:
        return []
    symbol_tables = [
        table for table in data.tables
        if table and any("符号" in cell for cell in table[0])
    ]
    if not symbol_tables:
        return [Finding("warning", "公式符号", "存在公式但未识别到符号表", "人工核对全部符号定义。")]
    defined = {
        symbol
        for table in symbol_tables for row in table[1:]
        for symbol in SYMBOL_PATTERN.findall(row[0] if row else "")
    }
    used = set(SYMBOL_PATTERN.findall(" ".join(data.formulas)))
    common = {"e", "i", "j", "k", "l", "m", "n", "s", "t", "x", "y", "z"}
    missing = sorted(used - defined - common)
    if not missing:
        return []
    return [Finding(
        "warning", "公式符号", "可能未定义：" + "、".join(missing[:30]),
        "该项为候选检查；结合上下标、集合和运算符人工复核。",
    )]


def check_abstract_numbers(paragraphs: list[str]) -> list[Finding]:
    abstract: list[str] = []
    body: list[str] = []
    in_abstract = False
    for paragraph in paragraphs:
        compact = paragraph.replace(" ", "")
        if compact.startswith("摘要"):
            in_abstract = True
        elif in_abstract and re.match(r"^(关键词|关键字)", compact):
            in_abstract = False
        elif in_abstract:
            abstract.append(paragraph)
        else:
            body.append(paragraph)
    numbers = set(NUMBER_PATTERN.findall(" ".join(abstract)))
    unmatched = sorted(number for number in numbers if number not in " ".join(body))
    if not unmatched:
        return []
    return [Finding(
        "warning", "摘要数字", "正文未检索到：" + "、".join(unmatched[:20]),
        "核对摘要、正文、表格和结果注册表的数值口径。",
    )]


def check_identity(text: str, metadata: dict[str, str], user_path: str = "") -> list[Finding]:
    findings: list[Finding] = []
    if any(value.strip() for value in metadata.values()):
        findings.append(Finding("warning", "匿名信息", f"文档元数据：{metadata}", "清除身份和软件元数据。"))
    for key in IDENTITY_KEYS:
        if key in text[:2500]:
            findings.append(Finding("warning", "匿名信息", f"论文前部出现“{key}”", "核对是否泄露身份。"))
    if user_path and user_path.lower() in text.lower():
        findings.append(Finding("blocker", "路径匿名", user_path, "删除本机用户路径。"))
    return findings


def flatten_numeric(data: Any, prefix: str = "") -> dict[str, float]:
    output: dict[str, float] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            output.update(flatten_numeric(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            output.update(flatten_numeric(value, f"{prefix}[{index}]"))
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        output[prefix] = float(data)
    return output


def load_results(path: Path) -> dict[str, float]:
    if path.suffix.lower() == ".json":
        return flatten_numeric(json.loads(path.read_text(encoding="utf-8-sig")))
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return flatten_numeric(list(csv.DictReader(stream)))
    raise ValueError(f"仅支持 JSON/CSV：{path}")


def compare_results(registry: Path, result_files: list[Path], tolerance: float) -> list[Finding]:
    reference = load_results(registry)
    leaves: dict[str, list[tuple[str, float]]] = {}
    for key, value in reference.items():
        leaves.setdefault(key.split(".")[-1], []).append((key, value))
    findings: list[Finding] = []
    for path in result_files:
        for key, value in load_results(path).items():
            candidates = leaves.get(key.split(".")[-1], [])
            if len(candidates) != 1:
                continue
            ref_key, ref_value = candidates[0]
            if abs(ref_value - value) > tolerance * max(1.0, abs(ref_value), abs(value)):
                findings.append(Finding(
                    "blocker", "代码结果—注册表",
                    f"{path.name}:{key}={value}，注册表{ref_key}={ref_value}",
                    "重新运行唯一最终入口，并同步注册表、图表和正文。",
                ))
    return findings


def make_report(findings: list[Finding], inputs: dict[str, str]) -> str:
    blockers = sum(item.severity == "blocker" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    lines = [
        "# 数学建模论文完整性初筛", "",
        f"- 阻断项：{blockers}", f"- 警告项：{warnings}",
        f"- 输入：{json.dumps(inputs, ensure_ascii=False)}", "",
        "自动初筛不能替代人工复核模型机理、数据边界、结论强度和最终版式。", "",
    ]
    if not findings:
        lines.append("未发现自动规则可识别的问题。")
    for index, item in enumerate(findings, 1):
        lines += [
            f"## {index}. [{item.severity}] {item.check}", "",
            f"- 证据：{item.evidence}", f"- 处理：{item.action}", "",
        ]
    return "\n".join(lines)


def self_test() -> None:
    sample = "摘要\n收益为12.5万元。\n关键词：优化\n正文引用[1]。此处插入图。\n参考文献\n[2] 示例"
    findings = check_placeholders(sample) + check_citations(sample)
    assert any(item.severity == "blocker" for item in findings)
    assert any("正文引用[1]" in item.evidence for item in findings)
    assert any("参考文献[2]" in item.evidence for item in findings)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        registry, result = root / "registry.json", root / "result.json"
        registry.write_text('{"profit": 100}', encoding="utf-8")
        result.write_text('{"profit": 101}', encoding="utf-8")
        assert compare_results(registry, [result], 1e-9)
    print("self-test: pass")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--result-registry", type=Path)
    parser.add_argument("--code-result", type=Path, action="append", default=[])
    parser.add_argument("--page-limit", type=int)
    parser.add_argument("--user-path", default="")
    parser.add_argument("--tolerance", type=float, default=1e-8)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not any((args.docx, args.pdf, args.result_registry)):
        parser.error("至少提供 --docx、--pdf 或 --result-registry 之一。")

    findings: list[Finding] = []
    inputs: dict[str, str] = {}
    if args.docx:
        data = read_docx(args.docx)
        inputs["docx"] = str(args.docx)
        findings += check_placeholders(data.text)
        findings += check_citations(data.text)
        findings += check_caption_sequence(data.paragraphs)
        findings += check_symbol_candidates(data)
        findings += check_abstract_numbers(data.paragraphs)
        findings += check_identity(data.text, data.metadata, args.user_path)
    if args.pdf:
        pdf_text, pages, metadata = read_pdf(args.pdf)
        inputs["pdf"] = str(args.pdf)
        inputs["pdf_pages"] = str(pages)
        findings += check_placeholders(pdf_text)
        findings += check_identity(pdf_text, metadata, args.user_path)
        if args.page_limit and pages > args.page_limit:
            findings.append(Finding(
                "blocker", "页数", f"{pages}页超过限制{args.page_limit}页",
                "压缩正文并重新导出。",
            ))
    if args.result_registry:
        inputs["result_registry"] = str(args.result_registry)
        inputs["code_results"] = ", ".join(map(str, args.code_result))
        findings += compare_results(args.result_registry, args.code_result, args.tolerance)

    report = make_report(findings, inputs)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                {"inputs": inputs, "findings": [asdict(item) for item in findings]},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    if any(item.severity == "blocker" for item in findings):
        raise SystemExit(2)
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
