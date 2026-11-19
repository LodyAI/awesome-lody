---
title: Lody 编排者团队
description: 六个角色组成一条开发流水线：调查、实现、审查、验收和运维，写代码与放行分离。
authors:
  - name: yayoinoyume
    url: https://github.com/yayoinoyume
languages: [zh-CN]
tags: [development, code-review, collaboration, workflow, verification]
source: https://github.com/yayoinoyume/lody-baka-dev-team
resources:
  - roles/orchestrator.yaml
  - roles/investigator.yaml
  - roles/builder.yaml
  - roles/gate-reviewer.yaml
  - roles/verifier.yaml
  - roles/operator.yaml
---

# Lody 编排者团队

把开发任务拆给六个互不越权的角色：编排者只调度，建造者只写，审查者只拦，放行者只判 PASS。同一个 Agent 不能自己写、自己审、自己放行。

## 解决什么问题

单个 Agent 同时写代码和判断“完成”，容易把自测当成验证。这个组合把职责拆开：

| 角色 | 只做什么 | 不能做什么 |
|---|---|---|
| [编排者](roles/orchestrator.yaml) | 写任务书、派发、收结果、落 done | 不写代码、不判 PASS |
| [调查员](roles/investigator.yaml) | 只读取证 | 不写文件、不提方案 |
| [建造者](roles/builder.yaml) | 按白名单实现、提交分支 | 不合并、不发布 |
| [审查者](roles/gate-reviewer.yaml) | 只读审查 diff，只能 BLOCK | 不放行、不跑验收 |
| [放行者](roles/verifier.yaml) | 在干净提交上跑冻结验收命令 | 不改代码、不改标准 |
| [运维执行者](roles/operator.yaml) | 发布、回滚、服务器变更 | 不参与日常写代码 |

关键约束：

- 编排者不写代码，只派活。
- 建造者是唯一写者，提交到独立分支，不合并。
- 审查者只读 diff，结论只有 BLOCK 或 NO_BLOCK；BLOCK 时不能派放行者。
- 放行者在 detached checkout 上原样跑冻结命令，结论只有 PASS / FAIL / INCONCLUSIVE。
- 每个 PASS 绑定一个具体提交 SHA；代码再变，旧 PASS 作废。

## 与 Lody 的关联

整套流程只使用 Lody 的 Agent Roles 和会话派发：

- 编排者用 `lody_agent_role_list` 动态查找角色，不写死角色 ID。
- 单个任务用 `lody_session_create`，多个任务用 `lody_session_create_many`。
- 收结果时先看真实 diff，再看自述。
- 需要巡检时用 `lody_session_status_many` 一次拿全部状态。

不依赖外部服务、脚本或数据库。

## 所需环境

- Lody，且当前 Agent 可以调用 Lody 的 session 与 Agent Role 工具。
- 你自己的机器、项目和可用的 Agent 配置。
- 示例推荐使用 Pi（`pi`）、推理强度 `max`；这些是建议值，可以换成你实际可用的 Agent 和设置。
- 如果希望放行者在隔离目录里跑验收，项目需要是 git 仓库，且允许创建 worktree。

## 使用方法

1. 在 Lody 中依次创建 6 个 Role，名称和描述按 `roles/*.yaml` 填写。
2. 把 `prompts/*.md` 的正文分别复制到对应 Role 的默认指令。
3. 选择自己的机器和 Agent，按需采用或替换 `recommended` 里的设置。
4. 用「编排者」创建会话，给它任务目标和可执行的验收标准。
5. 编排者派发建造者；建造者交付后派审查者；审查者 NO_BLOCK 后再派放行者。
6. 只有放行者写 PASS 后，才把叶子任务标记为 done。

建议先从一个很小的任务开始，跑通“建造者 → 审查者 → 放行者”这条链，再扩展到多任务并行。

## 文件约定

提示词里出现 `docs/work/<任务号>/`、`docs/ledger.md`、`.work/checkouts/` 这些路径，是这套流程的目录约定，不是 Lody 的强制路径。可以按项目习惯替换，但要保证所有角色写在同一个项目根下，否则下游看不到上游的产物。

任务材料建议固定为：

```text
docs/work/<任务号>/brief.md      编排者写的任务书
docs/work/<任务号>/evidence.md   调查员的证据包
docs/work/<任务号>/report.md     建造者的交付报告
docs/work/<任务号>/review.md     审查者的结论
docs/work/<任务号>/verdict.jsonl 放行者的验收记录
```

## 来源与许可

原创配置，以 MIT 提交。公开仓库：https://github.com/yayoinoyume/lody-baka-dev-team

这是一个手工配置组合：本仓库不提供自动导入器，不创建 Role，也不绑定机器。换一台机器或换一个 Agent 时，需要自己重新选择环境和设置。收录不代表维护者验证了运行效果。
