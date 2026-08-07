# 数学建模 Skills 目录规则

本目录仅维护八个通用数学建模 Skills，不为单届赛题、单个应用或单次错误新增重复 Skill。

读取或更新 `modeling-scientist`、`modeling-design`、`data-preparation`、`model-implementation`、`model-evaluation`、`figure-generation`、`paper-writing` 或 `paper-review` 时，除各 `SKILL.md` 已列出的参考文件和工作区根目录 `AGENTS.md` 外，还必须完整读取：

- `shared-references/agent_runtime_protocol.md`
- `shared-references/artifact_build_release_protocol.md`
- `shared-references/rule_authority_index.md`
- `shared-references/quality_gate_protocol.md`
- `shared-references/user_delivery_contract.md`

前两者负责阶段状态、输入完整性、产物追踪、恢复、运行模式、真实进度、环境预检、候选版本晋级、回滚和模板卫生；规则索引指定专项权威来源和按需加载范围；质量门禁规定生成—审查—修复闭环；用户交付契约记录当前用户的稳定偏好。专项模型、数据、评价、图表、写作和审核规则继续由原有Skill及其权威参考文件负责，不在此重复，也不得无任务地批量加载全部历史规则。

从外部 Agent 或软件中学习经验时，先分类为可迁移原则、软件专属实现、题目专属事实或高风险反例。只写入尚未覆盖且经过冲突筛选的可迁移原则；软件名称、历史题目字段、固定参数、固定数量和未经当前题目验证的结论不得进入通用 Skills。
