---
name: lody-update
description: 检查 Lody daemon 的版本和归属、桌面端更新缓存，升级独立 daemon，或将内置服务切换为独立 daemon。用户询问版本、更新命令、桌面端与 daemon 版本差异或切换运行方式时使用。
---

# Lody update

按请求选择检查、升级或切换。示例针对 macOS；其他系统先确认当前 CLI 帮助、安装路径和进程管理方式。只询问命令时直接提供命令，不执行升级。

## 识别目标与归属

先确认目标电脑；本地 shell 只能证明当前机器的状态。远程机器优先使用可用 Lody MCP 的发现能力，依据工具描述选择支持的操作。远程机器在线不代表已经具备远程 shell 或升级接口。

发现工具时先筛选工具名称，再读取相关工具的完整描述；避免一次输出全部 Lody 工具说明。

在目标机器执行：

```bash
hostname
command -v lody
lody --version
lody daemon status
cat ~/.lody/run/daemon.json
```

结合活跃进程判断归属：

- `Daemon is running` 且有 `lody daemon-runner`：独立 daemon。
- `Local agent Host: electron process …` 且服务入口位于 `Lody.app` 资源目录：桌面端内置服务。此时 `Daemon is not running` 只表示没有独立 daemon。
- 状态矛盾时检查对应 PID、父进程和启动入口；残留 PID 文件不能证明服务正在运行。

`lody --version` 是命令入口的安装版本。运行版本需结合 `daemon.json` 的版本、活跃 Worker PID 和运行状态验证；watchdog 与 Worker 可以使用不同 PID。

## 桌面端更新缓存与版本差异

升级 daemon 或切换运行方式且涉及桌面端时，分别确认桌面端安装版本、已缓存更新版本、daemon 实际运行版本。独立 CLI 和桌面端分别发布与安装，npm 升级不会替换桌面端；普通重启也不保证升级。

macOS 默认安装位置的版本可读自：

```bash
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' /Applications/Lody.app/Contents/Info.plist
```

实际位置和 bundle ID 以目标安装为准。稳定版常用 Sparkle 缓存目录为 `~/Library/Caches/ai.lody.desktop/org.sparkle-project.Sparkle/`。检查 `Installation`、`PersistentDownloads` 中的更新产物，若存在展开的 `Lody.app`，读取其 `Contents/Info.plist` 验证目标版本。`Launcher/Updater.app` 只是更新器，不是新版 Lody 的证据。

区分证据强度：

- 安装目录版本：当前磁盘上的桌面端版本；若运行期间发生替换，还需区分已运行进程版本。
- 缓存的完整应用或下载包：更新产物存在。缓存可能残留、未完成或安装失败，不能单凭文件名宣称已准备安装。
- 更新器报告 `downloaded` / `update-downloaded` 及对应版本：已下载的更新状态；按产品提供的安装更新操作完成安装。
- 安装完成并重开后核对版本：才证明升级生效。缓存清空或进程重启本身不足以证明成功。

没有找到缓存时报告“未发现已缓存更新”，而不是断言没有新版；需要时通过正常更新检查取得下载状态。检查请求只做读取，不顺带重启、安装或操控界面；遵守用户已有的 Computer Use 停止指示。

daemon 高于桌面端时明确报告版本差异。版本不一致本身不等于不兼容，兼容性需结合当前协议能力、实际连接或产品明确约束验证。不要为了对齐版本自动降级 daemon 或更新桌面端；按用户指定目标操作，并在无法确认兼容时说明尚未验证。

## 升级独立 daemon

先确认用户要求的版本；未指定时查询 npm 当前 `latest`，不要把历史版本或 `next` 当成最新稳定版。使用同一用户、Node/npm 环境安装，并保留原有启动参数和配置。

1. 查询 `npm view lody dist-tags --json` 解析目标稳定版本，再查询 `npm view lody@<目标版本> engines --json`。安装前核对实际 Node/npm 环境；运行时不满足要求时先处理依赖，保留旧服务。依赖升级应明确影响范围，避免连带升级无关工具。
2. 用 `npm install -g lody@<目标版本>` 安装，通过 `npm prefix -g` 获取稳定 launcher。macOS 通常为 `<prefix>/bin/lody`。验证实际 Node 满足安装包的 `engines.node`，且 `lody --version` 达到目标。核对原 watchdog、Worker 参数；旧 npx 部署也用稳定入口重启整个 watchdog。
3. 停机前用目标 CLI 的只读后端命令检查凭据可用性，例如先确认当前帮助支持 `workspace list --json`，再检查它能读取原工作区。它不是专用鉴权检查，也不能保证稍后的启动鉴权一定成功。旧 daemon 显示 connected 不能替代这一步；不要虚构 CLI 验权子命令。
4. 桌面端仍运行时，先正常退出并等待主进程结束，再停止 daemon。桌面端可能在 daemon 停止后自动接管 Host。若退出超时，保留服务，不强杀。
5. 停止成功后启动 daemon。只对明确可重试的临时 HTTP 错误做有界重试；每次重试前重新观察 Host。启动请求可能已接受，若目标服务正在运行则等待验证，不再次启动。401/403、Host 竞争或归属不明时停止重试；不自动重新登录、清凭据或加 `--skip-auth-check`。
6. 按下方验收标准验证服务，再重新打开先前运行的桌面端。等待主进程出现后再次验证，重读桌面端安装版本；正常退出可能触发已缓存更新安装。恢复时分别报告独立 daemon 与桌面端状态，打开应用不等于独立服务恢复。

macOS 默认启动参数的独立 daemon 可用 [scripts/restart_daemon.py](scripts/restart_daemon.py)，先安装目标 CLI，再执行：

```bash
python3 <skill目录>/scripts/restart_daemon.py --launcher /opt/homebrew/bin/lody --version <目标版本> --machine-id <已核实机器ID> --task-dir <新的绝对任务目录> --detach
```

脚本用于标准 npm launcher 和云端独立 daemon，不安装 npm 包，也不切换内置 Host。它在停机前检查 Node engine、旧服务归属与目标 CLI 的工作区读取，再退出桌面端、重启 daemon、验证连接并重开桌面端。临时 HTTP 408/429/5xx 最多尝试三次，重试间隔为 2、5 秒；每次启动前都检查归属。提供 `--app`、`--data-dir` 可指定实际路径，后者同步到 CLI 环境；`--check-only` 只验证、不重启。自定义 launcher 或启动参数需单独核实，不能用默认脚本替换配置。

`--detach` 返回任务 PID 和目录；保留这个原句柄。目录含 `task.pid`、`task.log`、原子写入的 `progress.json` 与 `result.json`。会话恢复后主动读取原任务结果，不等用户追问；结果缺失时查看原 PID、阶段和日志，不重新提交同一操作。

结果分别记录 `cliInstalled`、`restartCompleted`、`daemonVerified`，以及 `startAttempts`、失败阶段和恢复后的实际归属。`ok: true` 仅在最终验收完成后写入。若恢复快照显示旧版独立服务健康，或只重开了桌面端而归属变成 electron，应分别说明；后续用户手动恢复不能改写原任务失败的事实。脚本不会自动降级或把恢复请求当成恢复成功。

脚本按当前英文 CLI 状态字段解析；格式变化或证据缺失会失败，不猜测成功。必要时按当前 CLI 帮助适配。修改脚本后运行 `python3 <skill目录>/scripts/test_restart_daemon.py`；测试隔离所有进程和服务操作。用户自有自启脚本仅在请求涉及自启时修改。

当前若为内置服务，说明更新 npm CLI 不会更新内置服务。按用户意图更新桌面端或执行下方切换；升级请求本身不意味着改变运行方式。

## 升级验收

升级成功需要目标运行版本、预期 Host 归属、活跃 Worker 与 watchdog 对应关系，以及 `ready`、`online`、`authorized`、后端和原有工作区全部 connected。桌面端原先运行时，重开后再次检查这些状态。`ready` 和 `online` 可能早于后端连接，需有界等待。

验收不发送聊天消息、不新建 Agent 会话，也不触发模型或 ACP 能力探测。聊天可用性不属于升级成功条件；日志中已有的 Mirror/ACP 故障另行诊断，不因此反复重启、增大启动并发或修改用户会话。

## 内置服务切换为独立 daemon

1. 准备全局 CLI，验证版本及已有身份是否可用。已安装且满足请求时直接复用；切换本身无需升级。保留数据目录、机器身份、工作区、登录信息和服务端配置。
2. 告知切换会短暂中断连接。完全退出桌面端，等待已核实的 Electron 主进程及其内置服务释放 Host；只关闭窗口可能仍留有后台进程。
3. 用稳定 launcher 执行 `daemon start`，保留必要的原启动选项。沿用已有登录；需要新的交互认证时停在认证步骤。
4. 验证独立 Host、实际运行版本和就绪状态后，重新打开桌面端。
5. 再次确认仍由 `daemon-runner` 管理，桌面端连接现有服务。连接外部服务的能力以当前构建为准；出现占用冲突时报告证据，不启动第二份竞争服务。

这只完成当前运行方式切换。开机自启是单独任务，不自动创建 LaunchAgent、修改系统登录项或承诺重启电脑后仍会独立运行。

## 当前会话依赖被重启或切换的服务时

先准备恢复路径，再停止进程。必要时将“退出桌面端 → 等待退出 → 启动 daemon → 验证 → 重开桌面端”交给脱离当前会话生命周期的后台任务，保存任务句柄、日志路径和最终结果。

- 执行时发现并核实 PID、入口和版本，脚本中不复用历史会话的 PID。
- 对退出等待、启动和验证设置合理时限；保留工具原句柄，区分调用返回、等待超时和进程结束。
- 从 Electron/Agent 环境启动独立服务时，清除继承的会话身份、Electron bootstrap 和 supervisor 专属变量；保留安装环境、数据位置、服务端地址和实际需要的配置。重开桌面端时清除 `ELECTRON_RUN_AS_NODE`。
- 首选正常退出或对已核实目标发送正常终止信号。超时后记录阻塞，不自动强杀、清空数据目录或删除凭据。
- 切换失败时记录失败阶段并恢复桌面端可用性。后台任务已提交不等于操作成功；恢复连接后主动读取原任务结果，完成最终验证和报告。会话被中断时，保留任务目录供恢复后接续；不要以重新提交任务代替读取结果。

## 远程更新与完成证据

若使用 Lody 界面的“更新并重启”，核对目标机器与版本后提交一次。完成必须看到该机器重新上线且版本达到目标；在线、按钮已点击或 npm 安装成功都不足以证明运行服务已更新。

用户停止检查或停止 Computer Use 后，停止对应操作。未取得最终证据时明确说“已提交，尚未确认成功”。

交付时简要报告目标机器、实际运行版本、独立或内置归属、ready/online 与连接状态；只报告已验证事实，并说明待确认结果。
