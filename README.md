# MCM-Agent

一套面向全国大学生数学建模竞赛场景的通用 Agent Skills。它把数据准备、建模设计、实现、评价、制图、论文写作和终审串成可追溯的工作流，帮助 Agent 从题目与附件出发，形成可复现的分析过程和可交付的论文支撑材料。

本仓库提供的是可复用的工作规范、检查清单和辅助脚本，不包含任何具体赛题的答案、数据或预设结论。

## 包含的 Skills

| Skill | 作用 |
| --- | --- |
| `data-preparation` | 审查输入、定义数据口径、清洗并锁定可复用数据版本。 |
| `modeling-scientist` | 规划整体研究路线、问题拆解与跨阶段证据链。 |
| `modeling-design` | 建立假设、候选路线、验证设计和模型接口。 |
| `model-implementation` | 将模型实现为可复现的计算过程，并登记结果与运行证据。 |
| `model-evaluation` | 评价性能、稳健性、适用边界和结论强度。 |
| `figure-generation` | 生成服务于论证任务的图表与流程图。 |
| `paper-writing` | 基于已验证的证据完成竞赛论文写作。 |
| `paper-review` | 对数据、模型、结果、图表与论文进行独立终审。 |

`shared-references` 保存这些 Skills 共用的运行、发布、质量门禁、证据与写作规则；`scripts` 则提供版本清单、完整性校验和安全同步工具。

## 目录结构

```text
skills/
├── AGENTS.md                         # 套件级使用规则
├── data-preparation/                 # 八个通用 Skills
├── figure-generation/
├── model-evaluation/
├── model-implementation/
├── modeling-design/
├── modeling-scientist/
├── paper-review/
├── paper-writing/
├── shared-references/                # 共同协议与权威参考
└── scripts/                          # 校验、版本清单与同步脚本
```

## 快速开始

1. 克隆仓库，并在使用前阅读 [skills/AGENTS.md](skills/AGENTS.md)。
2. 根据当前任务选择一个或多个 Skill；每个 Skill 的 `SKILL.md` 说明其适用范围、输入、输出和必读参考资料。
3. 涉及真实题目时，先保存题面、附件、数据版本、运行配置和结果来源；不要用历史案例或未经运行的结果替代当前证据。
4. 在发布或部署前运行完整性校验：

   ```powershell
   python .\skills\paper-review\scripts\validate_skill_suite.py skills
   ```

校验成功会输出 `status=pass`；它验证套件结构与规则引用，不替代对数据、模型和论文内容的人工审查。

## 安全同步到其他环境

仓库自带的同步脚本会先复制到候选目录、校验通过后再原子替换目标，并保留旧版本备份。先用 `-WhatIf` 预览：

```powershell
.\skills\scripts\sync_workbuddy_skills.ps1 `
  -TargetSkillRoot 'D:\target\skills' `
  -WhatIf
```

确认后移除 `-WhatIf` 执行。目标目录必须与本仓库的 `skills` 目录分离，且仅包含该套件管理的内容；脚本会拒绝符号链接和非受管文件，避免误覆盖其他资料。

## 运行环境

- Skills 本身主要是 Markdown 与 Python/PowerShell 辅助脚本。
- 数学建模项目的默认协作偏好是 MATLAB 负责数据处理、建模与求解，Python 负责论文图表绘制；实际解释器、版本、Toolbox 与依赖须由具体项目的环境预检确定。
- `skills/figure-generation/requirements.txt` 列出制图场景可能需要的 Python 依赖。只在确有制图任务时安装，并使用项目隔离环境。

## 使用边界

- 以当前题面、附件、官方规则和真实运行结果为准；不要虚构数据、引用、结果或最优性结论。
- 规则只提供方法与检查框架，不替代参赛者的判断、验证和对当届规则的确认。
- 提交前仍应独立核验匿名要求、官方模板、AI 使用披露要求以及所有结果的可追溯性。

## 贡献与校验

修改任何 Skill 后，请至少运行：

```powershell
python .\skills\paper-review\scripts\validate_skill_suite.py skills
git diff --check
```

请将通用、经验证且可迁移的原则写入相应权威规则文件；不要把单届赛题事实、固定参数、私有数据或未经验证的经验写入通用 Skills。
