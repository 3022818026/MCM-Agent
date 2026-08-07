# 规则权威归属与按需加载索引

本索引是八个通用Skills的唯一规则导航页。它不重复具体规则，而是说明每类规则的权威来源、责任阶段和加载条件。发生冲突时依次服从：用户最新明确要求、数学与数据正确性、题目与官方规则、当前项目证据、权威规则源、历史经验。

## 常驻基线

任何数学建模Skill均完整读取：`agent_runtime_protocol.md`、`artifact_build_release_protocol.md`、`rule_authority_index.md`、`quality_gate_protocol.md`和`user_delivery_contract.md`。前两者分别规定项目状态与恢复、候选发布与环境预检；本索引规定专项规则的权威来源；质量门禁规定生成—审查—修复闭环；用户交付契约记录当前用户的交付偏好。它们不替代专项建模判断。涉及事实性结论时，按需加载`evidence_claim_discipline.md`。

## 规则权威来源

| 规则主题 | 唯一权威来源 | 责任阶段 | 其他文件的处理方式 |
| --- | --- | --- | --- |
| 题面语义、假设和模型粒度 | `common_modeling_principles.md` | 设计 | 只引用，不复制完整条款 |
| 候选路线、公平比较和验证证据 | `evaluator_review_principles.md` | 设计、评价、终审 | 专项Skill只说明本阶段动作 |
| 模型比较的适用与放弃条件 | `model_comparison_decision_rules.md` | 设计、评价 | 不固定比较数量 |
| 代码—模型映射、结果注册、传播与支撑材料 | `common_code_requirements.md` | 实现 | 写作、图表和审核只调用登记结果 |
| 论文图表任务、视觉自审和比较图选择 | `common_figure_requirements.md` | 制图 | 正文只解释图表结论 |
| 论文结构、摘要和信息归属 | `common_writing_requirements.md`与`paper-writing/references/competition_prose_style.md` | 写作 | 只规定章节功能、信息位置和竞赛化叙述契约；不得覆盖语言总标准 |
| 论文正文的语言质量、语义锁和修订边界 | `academic_style_revision.md` | 写作、终审 | 论文正文语言与语义规范的最高权威；结构建议、历史范例和表达骨架均不得覆盖 |
| 外部学术终审经验的可迁移检查 | `supervisor_review_lens.md` | 终审 | 仅补充语义忠实、论证链、分节职责、引用和图表的审查透镜；不作为当前题目证据、模板或硬性竞赛要求 |
| Word公式输出 | `paper-writing/references/word_formula_output_protocol.md` | 写作 | 不在其他文件维护命令白名单 |
| 续写前检查、数字/符号/引用/版式门禁 | `paper_integrity_gate.md` | 写作、终审 | 其他Skill只触发回退 |
| 阶段推进与失败回退 | `competition_workflow.md` | 全程 | 不替代各阶段的科学判断 |
| 历史案例隔离和经验迁移 | `historical_memory_usage_rules.md`与`project_learning_loop.md` | 全程 | 只迁移经复核的通用方法 |
| 事实主张、引用、外部资料、结果与措辞强度 | `evidence_claim_discipline.md` | 设计、评价、写作、终审 | 不在局部Skill重复维护来源分级 |
| 阻断项、高风险项、可自动检查边界、早停和问题台账 | `quality_gate_protocol.md` | 全程关键门禁 | 专项规则指定检查内容与责任Skill |

## 按需加载矩阵

| Skill | 专项必读 | 仅在触发时读取 |
| --- | --- | --- |
| `modeling-scientist` | `common_modeling_principles.md`、`evaluator_review_principles.md`、`competition_workflow.md`、`quality_gate_protocol.md` | 比较、数据、实现、写作或终审的专项规则与外部资料 |
| `modeling-design` | `common_modeling_principles.md`、`evaluator_review_principles.md`、`model_comparison_decision_rules.md`、`quality_gate_protocol.md` | 历史学习、深度学习专项、外部资料边界与证据主张 |
| `data-preparation` | `common_code_requirements.md`、`common_modeling_principles.md` | 复杂异常、数据来源说明、建模风险或历史经验 |
| `model-implementation` | `common_code_requirements.md`、`paper_integrity_gate.md`、`quality_gate_protocol.md` | 特殊模型原理、复杂失败诊断或结论传播 |
| `model-evaluation` | `evaluator_review_principles.md`、`model_selection_and_evaluation.md`、`quality_gate_protocol.md` | 多模型比较、外部事实、特殊题型或历史风险 |
| `figure-generation` | `common_figure_requirements.md`、`quality_gate_protocol.md` | 正文位置、结果传播、复杂比较统计或参考图复现 |
| `paper-writing` | `common_writing_requirements.md`、`paper_integrity_gate.md`、`academic_style_revision.md`、`evidence_claim_discipline.md`和`paper-writing/references/word_formula_output_protocol.md` | 模型比较、外部事实或历史句法参考 |
| `paper-review` | `paper_integrity_gate.md`、`evaluator_review_principles.md`、`academic_style_revision.md`、`quality_gate_protocol.md`、`evidence_claim_discipline.md`、`supervisor_review_lens.md` | 图表、数据或代码专项复核；用户提供外部学术规范目录时复读相关原始规则 |

读取条件不明确时，优先读取相应权威来源；不得为了省上下文跳过常驻基线，也不得无任务地批量加载全部历史文件。

## 维护与部署

- 通用规则只在本文件所列权威来源中维护；其他Skill发现规则冲突时标记来源并修改权威文件，不在局部重复打补丁。
- 通用Skills的版本与完整性由目录级清单、文件哈希和`paper-review/scripts/validate_skill_suite.py`验证，不向`SKILL.md`前置字段增加非标准`version`键。
- 部署到其他Agent前，使用`scripts/sync_workbuddy_skills.ps1`复制整个目录并验证；不得只复制八个`SKILL.md`而遗漏共享参考、公式协议或脚本。
