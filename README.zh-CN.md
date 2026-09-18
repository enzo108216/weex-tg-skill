# WEEX Daily Rebate → Telegram

使用说明语言：中文（本文）｜[English](README.md)｜[Telegram 多语言文案](telegram_push_copy.md)

这是一个本地 Python 应用（Windows/macOS 提供 GUI，Linux 等环境可使用 CLI）：通过官方 [weex-agent-skills](https://github.com/weex-labs/weex-agent-skills) 仓库中的 `weex-partner-skill` 只读 CLI 获取每日 Partner 返佣记录，严格聚合后推送到 Telegram 群组。本项目只修改自身代码，不修改或复制外部 skill 的 REST、签名、Vault 或 API profile；WEEX 凭据继续由外部 skill 管理。

本 skill 只负责 Telegram 配置、返佣结果聚合、发送和幂等。涉及 WEEX 账号添加/配置、API key、Vault、签名、REST/API、交易、分析或监控时，必须先读取并遵循对应的 `weex-trader-skill`、`weex-partner-skill`、`weex-analysis-skill` 或 `weex-monitor-skill`，不能依据本项目内容推断或直接操作。混合请求需要按职责拆分。

## 用 AI 一句话安装和配置

在支持 skills 的 AI 工具中，直接发送：

```text
从 https://github.com/enzo108216/weex-tg-skill 安装 WEEX Telegram Push skill，
先检查当前配置，再帮我配置一个定时 TG 推送。尽量复用已有 Bot、群组和 WEEX
profile，只询问缺失项；不要在聊天或日志中暴露 token；写入或发送前先给我摘要并确认。
```

安装后可以直接说：

```text
使用 $weex-tg-skill 查看我当前的 Bot、群组和推送任务。
```

```text
使用 $weex-tg-skill 为现有返佣任务配置每天上海时间 17:15 推送。
```

AI 仍会先执行只读预检、读取现有配置，并在写入配置或发送消息前单独确认；“一键”指一条自然语言请求完成引导，不代表跳过安全确认。

## 五个字段

- `Trading Volume = takerAmount + makerAmount`
- `Fee = sum(fee)`
- `Commission = sum(commission)`
- `Sub-affiliate Commission = sum(commission where sourceType == 2)`
- `Final Income = Commission - Sub-affiliate Commission`（公式显式展示，可配置）

默认按 UTC 自然日和 USDT 聚合；缺字段、partial、查询失败、混币或未知 sourceType 都不会发送。

Telegram 配置使用 SQLite 保存：同一个 Bot 可以绑定多个群，也可以配置多个 Bot；每个 `(Bot, Chat ID)` 绑定独立保存 WEEX profile 与查询口径。旧 JSON 配置不会迁移，新的 SQLite 数据库需要重新配置。

## CLI

```bash
# 0. 预检 GUI/CLI 能力，并查看只读发现的 Partner skill 路径
python -m weex_tg_bot doctor --json

# 1. 添加一个 Bot。Token 只通过 stdin 或环境变量传入，不放进命令参数
printf '%s\n' "$TELEGRAM_BOT_TOKEN" | python -m weex_tg_bot config set \
  --bot-name rebates \
  --skill-root /path/to/weex-agent-skills \
  --token-stdin

# 2. 维护独立群组目录（只保存群名称/Chat ID）
python -m weex_tg_bot config add-group -1001234567890 --group-name "返佣群"
python -m weex_tg_bot config add-group -1001234567891 --group-name "运营群"

# 3. 为已有 Bot/群组目录创建独立推送任务（GUI 任务编辑器或 CLI 都可建立关联）；profile/query/定时都属于任务
#    --timezone 是推送时区，查询窗口仍按 UTC 计算
python -m weex_tg_bot config add-task -1001234567890 \
  --bot-name rebates --task-name "每日返佣" --profile account-1 \
  --all-confirmed --schedule 09:00=1d --schedule 18:00=1w \
  --timezone Asia/Shanghai --language zh_cn
python -m weex_tg_bot config add-task -1001234567891 \
  --bot-name rebates --task-name "运营月报" --profile account-2 \
  --uids 10001,10002 --product-types SPOT --schedule 09:30=1m

# 自定义 N 天窗口必须给出 UTC 锚点日期
python -m weex_tg_bot config add-task -1001234567890 \
  --bot-name rebates --task-name "三日任务" --profile account-1 \
  --all-confirmed --schedule 23:00=3d@2026-09-01

# 另一个 Bot、查看/清理配置、测试 Telegram
printf '%s\n' "$TELEGRAM_BOT_TOKEN_OPS" | python -m weex_tg_bot config set --bot-name ops --token-stdin
python -m weex_tg_bot config add-group -1001234567892 --group-name "运维群"
python -m weex_tg_bot config add-task -1001234567892 --bot-name ops \
  --task-name "运维返佣" --profile account-ops --all-confirmed
python -m weex_tg_bot config show
python -m weex_tg_bot config find bot rebates
python -m weex_tg_bot config find group 返佣
python -m weex_tg_bot config clear-token --bot-name ops
python -m weex_tg_bot config remove-bot ops
python -m weex_tg_bot config remove-group -1001234567891
python -m weex_tg_bot test-telegram --bot-name rebates --chat-id -1001234567890

# 查看/安装/移除可选的用户级自动启动或桌面启动器（需要明确确认）
python -m weex_tg_bot startup status
python -m weex_tg_bot startup install --target autostart --confirm
python -m weex_tg_bot startup install --target desktop --confirm  # 仅 gui_capable=true
python -m weex_tg_bot startup remove --target autostart --confirm

# 手动交付必须明确选择目标 Bot/群组；send-result 只接收完整 Partner 结果
python -m weex_tg_bot send-result --date 2026-09-15 \
  --bot-name rebates --chat-id -1001234567890 --input partner-results.json

# 无 GUI 主机运行已启用的定时任务
python -m weex_tg_bot run

# GUI 路径（依赖缺失时先在用户选择 GUI 后安装隔离 runtime）
python -m weex_tg_bot gui-preflight --json
python -m weex_tg_bot gui-install --accept-managed-runtime
python -m weex_tg_bot gui --language auto
```

`config add-group` 只维护群组目录；`config add-task` 会从独立群组目录读取 Chat ID，并把 Bot/群组关联写入推送任务。GUI 的 Bot、群组和推送任务弹窗与 CLI 共用同一 SQLite 配置。

GUI 概览页支持按 Bot 名称、群名称或 Chat ID 查找，也可以删除选中的 Bot 或群组；删除 Bot 会同时删除其推送任务，删除群组会删除所有指向该 Chat ID 的推送任务。群组目录列只显示群名称和 Chat ID，profile、查询口径和定时设置属于推送任务列。

手动推送不是“发现已有配置就立即发送”。Agent 收到非定时推送请求时，必须先询问执行模式：

1. 执行已配置任务：列出自定义 Bot 名称、群名称、Chat ID、profile 和可用时间段，要求用户明确选择目标任务/窗口。
2. 临时查询：要求用户提供 UTC 开始/结束时间、profile、币种、产品类型、范围（明确确认全量下级或 UID 列表）、公式和目标 Bot/群组。

在模式和参数确认前，不查询 Partner、不使用“上一天”、首个 profile、全部绑定或全量下级等默认值，也不发送 Telegram。

用户只说“推送返佣到 TG”时，还必须先单独确认是“添加定时任务”还是“单次使用”。选择单次使用时不得创建或修改定时任务；选择添加任务后才进入 Bot、群组、profile、query、语言和 schedule 配置。

推送文案会在指标前展示本次查询上下文：触发方式、WEEX 账号 profile、查询范围、UTC 时间段、产品类型、结算币种和推送目标；随后展示五项指标、Final Income 公式和数据完整性状态。

示例：

```text
📊 WEEX 返佣统计

【查询信息】
触发方式：手动查询
WEEX 账号：合伙人
查询范围：全量下级（已确认）
查询时间（UTC）：2026-09-15 00:00:00 至 2026-09-15 23:59:59.999
产品类型：SPOT、FUTURES
结算币种：USDT
推送目标：rebates / 返佣群

【统计结果】
交易量（Trading Volume）：123,456.78 USDT
手续费（Fee）：12.3456 USDT
返佣（Commission）：98.7654 USDT
下级返佣（Sub-affiliate Commission）：10.0000 USDT
最终收入（Final Income）：88.7654 USDT

计算公式：Final Income = Commission - Sub-affiliate Commission
数据状态：完整
```

`config show` 永远分别显示 Bot、群组和推送任务：群组只包含名称/Chat ID，推送任务包含任务名、Bot、群组、profile、query、语言和定时设置。`--bot-name` 是 `--bot` 的明确别名，`--group-name` 是 `--label` 的明确别名；未填写群名称时推送文案回退显示 Chat ID。配置数据库默认位于 macOS 的 `~/Library/Application Support/weex-tg-skill/config.sqlite3`（Windows/Linux 使用对应配置目录），文件权限为 `600`；Telegram Bot token 默认直接保存到该 SQLite 数据库，不使用 macOS Keychain/Windows Credential Manager，也不需要额外明文存储确认。

GUI、CLI 和本 Skill 共用同一个 SQLite 配置源，不使用三套独立配置：

| 数据 | 所有者 | GUI 入口 | CLI/Skill 入口 |
| --- | --- | --- | --- |
| Bot 名称、Token、Partner skill 路径 | Bot 配置 | 概览 → 新建/编辑 Bot | `config set`、`config find bot` |
| 群名称、Chat ID | 独立群组目录 | 概览 → 新建/编辑群组 | `config add-group`、`config find group` |
| 任务名、Bot/群组目标、profile、query、语言、定时 | 推送任务 | 推送任务 → 新建/编辑 | `config add-task`、`config show` |
| 查询窗口、推送时间、IANA 时区 | 推送任务定时记录 | 任务编辑器 | `--schedule`、`--timezone` |

GUI 的实际流程是：概览页查找/管理 Bot 和独立群组；推送任务页选择已有 Bot、群组、profile、query、语言和定时后保存任务。GUI 保存后，CLI/Skill 立即从同一个 `config.sqlite3` 读取；CLI 修改 Token、群组或任务时也会保留 GUI 已保存的其他字段。GUI 打开期间由窗口内 scheduler 读取同一数据库，无 GUI 时使用 `run` 读取同一数据。

开始配置前先检测环境并让 AI 检索 Partner skill 候选路径：

```bash
python -m weex_tg_bot doctor --json
```

把 `doctor` 输出作为路由依据展示给用户。先看 `gui_capable`（由 `os`、`tkinter_importable`、`desktop_available` 决定）判断系统是否具备 GUI 基础能力；不能因为 managed runtime 未安装就直接把 GUI 排除。只要 GUI 基础能力满足，就用数字选项询问用户：

1. **使用 GUI**：打开配置窗口，由用户在界面中填写。
2. **帮我配置**：由 agent 逐步检查现有设置并协助填写，只在需要时询问一个选项。
3. **自己运行 CLI**：由 agent 提供命令，由用户在终端执行。

完成路线选择后，再进行窗口启动或配置写入。

`doctor --json` 的 `skill_root_candidates` 是只读发现结果。选择 GUI 或执行 `gui-install` 时，程序会先扫描当前 AI 工具暴露的 skill 根目录（包括 `*_SKILLS_ROOT`、`CODEX_HOME`、Codex vendor skills 和常见工具目录），验证 `weex-partner-skill/scripts/weex_partner_cli.py`；只有一个候选时自动写入 `skill_root`，多个候选时要求选择，找不到候选时停止并提示安装/暴露 Partner skill。CLI/GUI 不会静默选择多个候选。

用户选择 GUI 后，agent 会先完成 Partner skill 自动发现/配置；候选唯一时无需再次手填路径。若 managed runtime 缺失，再在后台执行 `python -m weex_tg_bot gui-install --accept-managed-runtime`，安装本 skill 自己的隔离依赖后再启动 `python -m weex_tg_bot gui --language auto`。该选择同时授权这次 skill 路径配置和 managed runtime 的本地安装及其联网依赖安装；安装失败时必须报告原因并明确提供 CLI 选项，不得静默切换或写入部分配置。不要把依赖安装到系统 Python。

只有在不支持的操作系统、无交互桌面或 Tkinter 不可用时才不提供 GUI，并提供两个数字选项：**2. 帮我配置**、**3. 自己运行 CLI**。不要尝试安装系统级 Tkinter/桌面组件或在 headless 会话启动 GUI。CLI 仍须在首次写入、token/群组变更或测试发送前取得确认，并通过 stdin/environment 处理 token。用户明确授权时，也可以直接在聊天中提交 token；此时不得回显、记录或把 token 放入命令参数。`recommendation=gui` 和 `recommendation=gui-install` 只是就绪提示，不能替代 GUI 基础能力判断和用户路线选择。

AI 可以直接帮用户执行 CLI 配置，但必须采用逐步引导：先读取并列出现有 Bot、群组和 WEEX profile，让用户选择；只有缺少对象时才询问一个新字段。随后再逐步确认 profile、产品/币种、UID 范围、语言和定时。Chat ID 可以在聊天中提供；用户明确授权时 Bot token 也可以直接贴到聊天中，但 agent 不得回显 token、把 token 放进命令参数或写入日志，只能通过本地 stdin 或环境变量使用。没有 WEEX profile 时转交 `weex-trader-skill`，Partner 产品/UID 能力缺失时转交 `weex-partner-skill`，不得强行猜测或兜底。

注意：TG 配置 GUI 与 WEEX 账号管理器是两个独立入口。打开 WEEX 账号管理器不等于已经授权 TG 配置写入。

GUI 使用本 skill 自己的 managed venv。窗口打开后只有“概览”“推送任务”“使用说明”三个主区域：概览展示 Bot 状态、群组目录、任务数量和调度数量，并提供查找、编辑、删除；Bot/群组新增和编辑均从概览打开模态弹窗。群组弹窗只维护群名称和 Chat ID，不直接保存 profile/query；推送任务弹窗负责 Bot/群组目标、profile、query、语言和定时。推送任务页还提供测试 Telegram 和立即发送。GUI 启动时会尝试获取共享 scheduler 锁；锁空闲时启动后台调度器，已有其他实例时仍可使用 GUI 但跳过自身 scheduler。保存后的任务会在任务时区的时间点自动检查并发送；关闭 GUI 后它拥有的调度器停止。任务弹窗中的 profile 来自已保存账号，币种/产品选项从官方 Partner skill 契约动态读取，仅作为提示，不构成本地允许列表；用户输入最终由官方 Partner skill 校验。UID 通过官方 `list-referral-uids` 加载，支持搜索和多选。勾选“全部下级”会禁用并忽略 UID 选择器。查询窗口支持上一完整自然日/周/月/年，以及排除当天的近 N 天多选；自定义 N 天必须选择 UTC 开始日期。推送时间使用任务时区下的小时/分钟选择器，默认 UTC，支持 IANA 时区和夏令时，保存时生成时间×查询窗口组合。修改群组 Chat ID 会同步任务目标，任务语言独立保存。右上角语言选择器会自动发现 `weex_tg_bot/locales/*.json`，启动时按系统 locale 自动选择；当前随包提供 `en_us`、`zh_cn`、`zh_tw`、`ko`、`ja`、`vi`、`id`、`th`、`fa_ir`、`ar`、`tr`、`de`、`fr`、`it`、`es_es`、`pt_pt`、`pl`、`ru`、`uk`、`az`、`es_419`、`es_ar`、`pt_br`，新增语言只需新增同 key 的 locale JSON 文件。RTL 语言（阿拉伯语、波斯语）会自动应用右到左文本方向。Telegram 文案与 GUI 共用同一套 key。

用户选择 GUI 且依赖缺失时，在后台执行：

```bash
python -m weex_tg_bot gui-install --accept-managed-runtime
python -m weex_tg_bot gui --language auto
```

安装目录位于用户级 `weex-tg-skill/gui-runtime/venv`，不会复用系统 Python 的 GUI 依赖。没有用户选择 GUI（或明确确认安装）时不会自动创建 venv 或安装依赖。

用户选择由 agent 直接配置时，按“预检 → 选择/新建 Bot → 选择/新建群组 → 选择现有 WEEX profile → 选择 Partner 能力和范围 → 设置语言/定时 → 展示摘要并确认 → 写入”的顺序推进，每轮只询问一个选择或缺失字段。然后用 `config set --bot-name NAME --token-stdin`/`--token-env` 添加 Bot、用 `config add-group CHAT_ID --group-name GROUP_NAME` 维护独立群组目录，再用 GUI 任务编辑器或 `config add-task` 创建任务。`send-result` 必须显式指定 `--bot-name` 与 `--chat-id`。若 token 是用户在聊天中明确授权提交的，也必须沿用 stdin/environment 路径，不能出现在命令参数或输出中。

Skill 加载完成后只做 `doctor --json` 与 `startup status` 只读检查。若用户希望登录后自动运行或桌面打开入口，必须单独确认后再执行 `startup install ... --confirm`；不得把 skill 发现事件本身当作系统自启授权。

定时任务写入后不会自动生效，必须有 scheduler 进程运行。Agent 要再次检查 `doctor --json` 和 `startup status`，让用户明确选择当前 GUI、登录后自启、桌面启动器、手动 `python -m weex_tg_bot run` 或暂不启用，并在用户选择后完成对应启用。GUI、开机自启、桌面启动器和手动 `run` 共用跨进程 scheduler 锁：第一个实例负责调度，GUI 检测到已有实例时只打开界面而跳过自身 scheduler，第二个 `run` 会正常退出。GUI 关闭会停止其自身 scheduler；自启安装从下次登录生效；`run --once` 会立即执行推送，不能当作健康检查。

选择“帮我配置”时按“预检 → 选择配置路线 → 收集自定义 Bot 名称、每个群名称/Chat ID、profile、query 和时间段 → 写入 SQLite → `config show` 验证 → 按需测试/发送”的顺序进行。缺少 Bot 名称、群名称、profile、Chat ID、明确全量 scope 或定时参数时只追问缺少项，不查询 Partner，也不写入部分假设配置。

## 两个 skill 的协作

安装官方 `weex-partner-skill` 与本项目 `weex-tg-skill` 后，手动流程是：

1. 先执行 `python -m weex_tg_bot config show`，确认至少有一个 Bot 已配置 token，且每个目标 Chat ID 都有独立的 profile/query 绑定；配置缺失时先完成 TG 配置，不查询 WEEX 数据。
2. 用 `$weex-partner-skill` 查询完整 `get-commission` 结果。
3. 将一个或多个产品类型的结果合并为 `{ "results": [ ... ] }`。
4. 执行带有 `--bot-name` 与 `--chat-id` 的 `send-result`，由本 skill 完成严格聚合和 Telegram 推送。

无人值守 `run` 模式会优先从 `WEEX_PARTNER_CLI`、`WEEX_AGENT_SKILLS_ROOT` 和常见 Codex skill 目录发现已安装 Partner CLI，也可以用 `--skill-root` 显式指定；它复用同一查询契约，不复制 Partner API。GUI 已打开时由 GUI 内置后台调度器负责检查；无 GUI 的主机仍可运行 `python -m weex_tg_bot run`。每个任务可保存多个 `HH:MM=1d|1w|1m|1y|Nd@YYYY-MM-DD` 时间段和 IANA 时区，推送时间按任务时区检查，查询窗口按 UTC 计算为上一完整自然周期（自定义 `Nd` 使用锚点日期）；`run --once` 只执行已启用的调度项。手动推送必须遵循上面的模式确认流程，并显式指定目标绑定。

## Skill 适配

`--skill-root` 应指向已安装官方 skill 中包含 `skills/weex-partner-skill/scripts/weex_partner_cli.py` 的本地目录。本项目不会自动修改、安装或拉取外部仓库；路径缺失时会在无人值守发送前失败并保持 fail-closed。可用 `PartnerClient(runner=...)` 注入 fixture 做离线测试。真实 Telegram Bot token、群组权限和双平台 GUI 启动属于集成验证，不由 fixture 代替。
