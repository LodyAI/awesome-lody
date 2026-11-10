---
title: Lody update
description: 检查 Lody daemon 的版本与归属、桌面端更新缓存，升级独立 daemon，或把桌面端内置服务切换为独立 daemon。
authors:
  - name: Edger
    url: https://github.com/Edger
languages: [zh-CN]
tags: [lody, daemon, update, maintenance, macos]
---

`lody-update` 是面向 Lody 日常维护的 Skill。它把“先确认目标机器和运行归属，再升级或切换”的判断步骤固定下来，避免把 CLI 安装成功、进程重启或缓存存在误当成升级完成。

Lody 发布新版本后，可以在 Lody 或其他支持 Skill 的 Agent 中使用它，对本地或远程机器发起升级，并验证目标机器重新上线且运行版本达到目标。

## 适用场景

- 查询 Lody CLI、独立 daemon 与桌面端的版本，判断服务实际由谁托管。
- 检查 macOS 桌面端更新缓存，区分“已下载”和“已安装生效”。
- Lody 发布新版本后，通过 Lody 或其他 Agent 远程升级 Lody，并确认目标机器恢复连接、版本达到目标。
- 升级全局安装的独立 daemon，并在重启后验证 Worker、连接和工作区。
- 将桌面端内置服务切换为独立 daemon，或排查两者之间的版本差异。

## 前提

- 目标机器已安装 Lody，并可通过本地 shell 或 Lody MCP 访问。
- 远程升级需要目标机器具备可用的 Lody MCP 或远程 shell；仅仅在线不代表已经具备远程升级接口。
- 升级独立 daemon 需要可用的 Node/npm 环境和全局安装权限；脚本会在停机前核对目标包的 `engines.node`，不满足时保留旧服务。
- 自动化重启脚本目前仅支持 macOS，需要 Python 3；其他系统按 [SKILL.md](SKILL.md) 的手动步骤执行。
- 执行前确认目标机器、目标版本和当前服务归属。

## 使用

1. 按所用 Agent 的 Skill 安装方式安装本目录。
2. 在 Lody 或其他支持 Skill 的 Agent 中选择该 Agent，并指向要维护的机器或项目。
3. 用自然语言说明目标，例如“检查这台机器的 Lody 版本和运行归属”，或“把远程机器上的 Lody 升级到最新稳定版并确认重新上线”。
4. 只查询版本时，Skill 只读取状态，不执行升级。需要重启服务时，先确认恢复路径，再按 [SKILL.md](SKILL.md) 的顺序执行。

## 安全边界

- 不把历史会话的 PID、机器 ID 或运行时状态写进脚本；执行时重新核实。
- 重启脚本在停机前检查旧服务归属、Node engine 和目标 CLI 能否通过 `workspace list --json` 读取原工作区；只对明确的临时 HTTP 408/429/5xx 做有限重试，401/403 或归属不明时停止。
- 后台任务会原子写入 `progress.json` 和 `result.json`；恢复连接后读取原任务，不重复提交同一操作。
- 退出桌面端超时后记录阻塞，不自动强杀、清空数据目录或删除凭据。
- 没有最终验证证据时，报告“已提交，尚未确认成功”，不把 npm 安装成功或按钮点击当作完成。
- 默认重启脚本只处理已存在的独立 daemon；不会安装 npm 包，也不会把内置 Host 当作独立 daemon 重启。

## 文件

- [SKILL.md](SKILL.md)：完整 Skill 指令。
- [scripts/restart_daemon.py](scripts/restart_daemon.py)：macOS 独立 daemon 重启与验证脚本，支持 `--check-only` 和 `--detach`，并写入 `progress.json` / `result.json`。
- [scripts/test_restart_daemon.py](scripts/test_restart_daemon.py)：使用 mock 隔离进程和服务操作的回归测试。
- [agents/openai.yaml](agents/openai.yaml)：Agent 界面显示名称与简介。
