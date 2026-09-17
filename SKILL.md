---
name: weex-tg-skill
description: Push complete daily WEEX Partner rebate results to Telegram through a manual or scheduled workflow with custom Bot and group names. Use together with the installed weex-partner-skill; this skill owns Telegram configuration, aggregation, delivery, and idempotency, not WEEX REST access.
---

# WEEX Telegram Push Skill

This skill is installed alongside `weex-partner-skill` from the official `weex-agent-skills` project.

## Required OS/UI routing

Before recommending, launching, or writing any Telegram configuration, run:

```bash
python -m weex_tg_bot doctor --json
```

Treat the `doctor` result as a user-visible routing decision, not an internal
check. Treat `gui_capable` (equivalent to `os` + `tkinter_importable` +
`desktop_available`) as the GUI capability check; a missing managed runtime
is a missing dependency,
not a reason to hide the GUI choice. Do not use `recommendation=command` alone
to force CLI when the desktop and Tkinter checks say that a GUI can run.

When the system is GUI-capable, present GUI and CLI routes and also tell the
user that the agent can perform the CLI setup for them. Ask which route to use
before any write or window launch:

- GUI: `python -m weex_tg_bot gui --language auto`. If
  `managed_runtime_ready` is false, install the missing skill-owned GUI runtime
  dependencies in the background with
  `python -m weex_tg_bot gui-install --accept-managed-runtime`, then launch the
  GUI. The user's choice of GUI authorizes this managed local setup and its
  network dependency install; do not ask for a second install confirmation or
  expose installation progress unless it fails. Never install into the user's
  system Python. If setup fails, report the error and offer CLI explicitly;
  never silently switch routes or write partial configuration.
- CLI: use the command path and configure secrets through stdin/environment or
  the local SQLite configuration store.
  Ask for confirmation before the first configuration write, token change,
  group change, or test send if the user's route choice did not already clearly
  authorize that operation.
- Agent-assisted setup: the agent can run the CLI steps on the user's behalf
  after authorization, but must guide the user one decision at a time. Do not
  ask for Bot name, token, Chat IDs, profile, query, and schedules as one batch.
  First inspect the current SQLite configuration and list existing Bot names;
  ask the user to choose an existing Bot or explicitly create a new one. Ask
  for a token only when the selected Bot has no token or the user requests a
  token change. Keep tokens secret and pass them only through stdin/environment.
  Next list existing standalone groups and let the user choose one; ask for a
  new group name/Chat ID only when no suitable group exists.
  After a Bot/group target is selected, inspect saved WEEX profiles through the
  owning `weex-trader-skill`; if no profile exists, route the user there and do
  not invent a profile name. Then inspect Partner products, coins, and referral
  UIDs through `weex-partner-skill`; if that skill is unavailable or the query
  fails, route to its rules and stop rather than guessing defaults. Ask for one
  missing query or schedule choice at a time, show a compact review, and obtain
  confirmation immediately before writing. Use `config set`, `config add-group`,
  and `config add-task` only after each corresponding choice is settled. The
  GUI creates the same records through its dialogs and shared SQLite store.

If the system is not GUI-capable (unsupported OS, no interactive desktop, or
Tkinter unavailable), explain the blocking preflight facts and offer CLI-only
routes, including agent-assisted CLI configuration.
Do not try to install a system Tkinter/desktop component or launch a GUI from a
headless session. Still ask for confirmation before CLI mutations. If the user
explicitly chose direct token submission, accept it for the current operation,
but keep it in stdin/environment and never echo or log it.

Use `recommendation=gui` as a ready-to-launch hint, and
`recommendation=gui-install` as a hint that the selected GUI route needs the
background managed-runtime install. The recommendation is subordinate to the
GUI-capability check and the user's route choice.

The TG configuration GUI (`python -m weex_tg_bot gui --language auto`) is separate from the
WEEX account/profile manager supplied by `weex-trader-skill`. A request to open
the WEEX account manager follows that skill's GUI/runtime rules and does not
authorize TG configuration writes.

Use a short route question that makes the available choice and side effect
explicit, for example:

> 预检结果：桌面和 Tkinter 可用。你要使用 GUI、自己运行 CLI，还是选择逐步配置？GUI 路径会先自动检索当前 AI 工具的 Partner skill 目录，再处理 GUI runtime；逐步配置路径会先列出现有 Bot、群组和 WEEX profile，每次只询问一个选择或缺失字段，不要求一次性填写全部信息。

For a GUI-capable system, one route question is sufficient: a GUI choice covers
Partner skill discovery/configuration, managed-runtime installation, and the
subsequent TG window launch. A direct
  agent-assisted choice covers the CLI setup only after the token delivery method
  and target groups plus their profile/query bindings are confirmed. A user choosing the WEEX account manager is
not a substitute for the TG route choice.

## Guided configuration flow

Use this flow whenever the user asks to configure, set up, enable, or repair
Telegram delivery. Keep the questions conversational; ask only for values still
missing after combining the current turn with earlier context.

### 1. Preflight and route authorization

Run `python -m weex_tg_bot doctor --json` first. Present the GUI/CLI/agent route
and its side effect. A direct “帮我配置/启用/修复” request authorizes the
configuration write, but not a test message unless the user asks for one. A GUI
choice authorizes the managed GUI runtime installation described above.

### Progressive prompting rules

The assistant must keep configuration conversational and incremental:

1. **Inspect before asking.** Run `config show`/`config find` and read-only
   discovery first. Present existing Bots, groups, profiles, Partner products,
   and UID candidates when available; do not ask the user to retype known data.
2. **One decision per turn.** Ask for at most one selection or one missing value
   at a time: route → Bot → group → WEEX profile → query scope/products →
   language → schedule → final review. If a value is already unambiguous and
   the user has authorized configuration, reuse it only after stating it.
3. **Route missing capabilities.** No saved WEEX profile means follow
   `$weex-trader-skill`; no Partner catalog/UID/query capability means follow
   `$weex-partner-skill`. Read that skill's rules and stop at its required input
   or confirmation step. Do not create fake profiles, invent UIDs, call an
   undocumented endpoint, or silently fall back to “yesterday”/all referrals.
4. **Review before write.** Once the individual choices are complete, show one
   compact summary of the Bot, group, profile, query, language, and schedule;
   ask for confirmation immediately before the corresponding write. Testing or
   sending Telegram is a separate confirmation.

### 2. Build the target binding set

First create or select a Bot, then create one or more standalone groups. Create
a separate push task that selects an existing Bot and group; the task owns the
Bot/group association, profile, query, language, and schedules, while the group
owns only its name/Chat ID relationship. The GUI Overview and `config show` must expose
Bot status, group catalog entries, task counts, and the one-to-many relationship.
Do not collect every field in one prompt. After the Bot and group are selected,
walk through the following choices one at a time; each push task keeps its own
profile/query/language/schedules and must not inherit a global default:

- A custom Bot name and Telegram Chat ID. The Bot name is the stable logical
  key and the human-readable name shown in task selection and messages; `main`
  is only a backward-compatible CLI default, not a value to infer during
  guided setup.
- A custom group name for the Chat ID. Store it with `--group-name`; if the
  user leaves it empty, display the Chat ID as the fallback. Never invent a
  group name from a profile or query.
- The saved WEEX profile for this push task. First list profiles from the
  owning `weex-trader-skill`; if the list is empty or unavailable, route there
  and stop. If it is ambiguous, ask the user to choose; never silently reuse an
  unrelated profile or ask them to guess a profile name.
- Query: first read the official Partner catalog and present available coin/
  product choices; then ask for scope (`--all-confirmed` or `--uids`) and formula
  (default `commission_minus_subaffiliate_commission`). Never infer all scope
  from a missing UID. If the Partner catalog or UID operation is unavailable,
  follow `$weex-partner-skill` instead of forcing a local fallback.
- Query windows and push times are separate. Query windows support `1d`, `1w`,
  `1m`, `1y`, and positive `Nd` windows; custom Nd requires a UTC start date
  and uses fixed anchored cycles. Select multiple windows. Push times are
  independent local `HH:MM` values with an IANA timezone (default UTC); the
  task expands selected time × window combinations into schedules and handles
  DST through zoneinfo. Query windows remain UTC. No schedule means manual-only
  delivery.

When schedules are requested, explain the natural-period meaning: `1d` is the
previous UTC day, `1w` the previous complete Monday–Sunday week, `1m` the
previous complete UTC calendar month, and `1y` the previous complete UTC calendar
year. The current day/week/month/year is never included. Do not ask for a fixed
start/end date for scheduled windows; they are calculated at execution time.

### 3. Collect and validate the Bot secret

Only ask for a Telegram Bot token after the user has selected a Bot that has no
stored token or has explicitly requested a change. Only ask for a Chat ID after
existing groups have been listed and the user chooses to create a new group.
Tokens may be supplied in chat only after the user explicitly authorizes that
route; otherwise use GUI, local stdin, or an environment variable. Never repeat
the token, put it in a command argument, or write it to logs. When direct chat
submission is explicitly authorized, allow the submitted token to be saved
through the normal mode-600 SQLite path; do not reject it or require rotation
solely because it appeared in the conversation.
If the user says the token was revoked or rotated, use the replacement token
they provide.

Before writing, confirm the target profile, Partner skill root, all group/task
parameters, and requested schedule entries. Bot tokens are stored in the mode-600
SQLite database by default; no OS keyring or extra plaintext opt-in is required.

### 4. Write configuration by binding

Use the CLI/GUI as the single configuration path:

1. `config set --bot-name NAME` stores the Bot token and the user-confirmed
   Partner skill root. `--bot NAME` remains a compatible alias.
2. `config add-group CHAT_ID --group-name GROUP_NAME` creates or replaces a
   standalone group catalog entry. It does not attach a profile or query;
   `--label` remains a compatible alias and `--group-name` is optional only when
   Chat ID fallback is explicitly acceptable.
3. `config add-task CHAT_ID --bot-name NAME --task-name TASK_NAME --profile PROFILE ...`
   creates or replaces an independent push task for an existing target. Repeat
   `--schedule HH:MM=PERIOD[@YYYY-MM-DD]` for multiple task windows and use
   `--timezone IANA/TZ` for the push clock.
4. Use `config show` and verify Bot/group associations and task targets before
   querying Partner. Do not query Partner data while a required task field is missing.

If a write fails, stop and report the failing group or task; do not continue with a
partially assumed configuration. Existing JSON configuration is not a source of
defaults and is never migrated.

### 5. Verify and hand off

Offer `test-telegram` only when the user wants an actual test message. For a
manual push, do not infer the date, account, scope, or target from whatever is
currently configured. First ask the user to choose one of these modes:

1. **Execute a configured task** — show the configured Bot name, group name,
   Chat ID, profile, and schedules, then ask which single task/window to
   execute. A configured
   task supplies its saved profile/query and its natural-period window; it must
   still be explicitly selected when more than one task is available.
2. **Run an ad-hoc query** — collect the UTC start/end time, saved WEEX profile,
   coin, product types, scope (`all` only after explicit confirmation or an
   explicit UID list), formula, and the target Bot/Chat binding. Do not fall
   back to “yesterday”, the first profile, all bindings, or all referrals.

Do not query Partner or send to Telegram until the mode and all required
parameters are confirmed. After confirmation, use `send-result` with an
   explicit `--bot-name` and `--chat-id` for the selected task. For unattended
 schedules, explain that the GUI starts its own background scheduler while the
 window is open; headless hosts must keep `python -m weex_tg_bot run` running
 (or launch it through the host OS). `run --once` executes all enabled schedule
 entries immediately.

If any Partner query, range segment, aggregation, Telegram send, or ledger write
fails, keep the operation fail-closed and report which binding/window was
affected. Never claim the whole push succeeded from a partial result.

### Telegram message template

Every delivered message must include the binding and query context before the
metrics so a reader can verify which account and scope produced the numbers:

```text
📊 WEEX 返佣统计

【查询信息】
触发方式：手动查询
WEEX 账号：<saved profile>
查询范围：<全量下级（已确认）或指定下级 UID：...>
查询时间（UTC）：<start> 至 <end>
产品类型：<SPOT、FUTURES>
结算币种：<USDT/BTC>
推送目标：<bot name> / <group name or chat id>

【统计结果】
交易量（Trading Volume）：<amount> <coin>
手续费（Fee）：<amount> <coin>
返佣（Commission）：<amount> <coin>
下级返佣（Sub-affiliate Commission）：<amount> <coin>
最终收入（Final Income）：<amount> <coin>

计算公式：Final Income = Commission - Sub-affiliate Commission
数据状态：完整
```

The scope must be rendered as a readable confirmed-all label or a sorted UID
list; never print the internal scope dictionary. The target line is rendered
per Bot/Chat binding using the configured custom names (falling back to Chat ID
only when no group name was configured), so identical queries sent to different
groups cannot carry the wrong destination context.

## Responsibility boundary

- Use `$weex-partner-skill` to query WEEX Partner data. Do not duplicate Partner REST signing, Vault handling, profile resolution, pagination, or query policy here.
- This skill receives the Partner result, validates completeness, computes the daily summary, and sends it to configured Telegram push tasks.
- SQLite is the source of truth for runtime configuration. Groups own only names/Chat IDs; each push task owns its Bot/group association, saved WEEX profile, query, language, and zero or more enabled schedules. A schedule is `HH:MM=1d|1w|1m|1y|Nd@YYYY-MM-DD` with an optional IANA timezone; the push clock uses that timezone while the window resolves to the previous complete UTC natural period (or an anchored custom `Nd` window), excluding the current day/week/month/year. Existing JSON and legacy binding rows are not read or migrated.
- Shared GUI/CLI/Skill data contract: `bots` stores Bot name and token, `groups` stores standalone Chat ID and display name, `push_tasks` stores task name/Bot/group/profile/query/language, and `push_task_schedules` stores the task's time × query-window × timezone entries. `config set`, `config add-group`, and `config add-task` preserve and update these same records; the GUI task editor and the headless `run` scheduler read them through `ConfigStore`.
- Telegram Bot tokens are managed by this project through the CLI/GUI. Direct
  token submission in chat is allowed only after the user explicitly authorizes
  it; never repeat, print, log, or place the token in a command argument.

## Cross-skill routing boundary

This skill is not the source of truth for WEEX account management or other
non-Telegram capabilities. Before answering or acting on a request outside this
skill, read and follow the installed skill that owns that capability:

| Request topic | Required skill route |
| --- | --- |
| WEEX account/profile creation, API keys, Vault, signing, REST/API setup, normal trading or account configuration | `$weex-trader-skill` |
| WEEX Partner referral, commission, referral assets, sub-agent, or relationship queries | `$weex-partner-skill` |
| PnL, fills, exposure, or risk analysis | `$weex-analysis-skill` |
| PnL monitoring or alerting | `$weex-monitor-skill` |

Routing rules:

1. Read the owning skill's `SKILL.md` and any required references before giving
   instructions or making a tool call for that topic. Do not infer its API,
   account, Vault, profile, endpoint, or credential behavior from this skill.
2. For a mixed request, split the Telegram delivery portion from the WEEX or
   analysis portion. Use this skill only for Telegram configuration,
   aggregation, delivery, and idempotency; hand the other portion to its owning
   skill first.
3. If the owning skill is unavailable or cannot be read, state that limitation
   and stop the out-of-scope portion rather than inventing an answer. A saved
   profile name or a successful TG configuration does not authorize WEEX account
   changes.

## Manual handoff

For a user-triggered push, the first response is a mode question, not a send:

> 你要执行已配置的哪个 Bot/群组任务，还是做一次临时查询？如果是已配置任务，我会先列出 Bot 名称、群名称、Chat ID、profile 和时间段；如果是临时查询，请提供 UTC 开始/结束时间、账号 profile、币种/产品、范围（全部下级或 UID 列表）和目标 Bot/群组。

If the user chooses a configured task, enumerate the current push tasks and
schedules and require one explicit selection (or an explicit request to run a
set of selected bindings). If the user chooses an ad-hoc query, collect and
echo the complete query contract for confirmation before any Partner call.
Never treat the existence of a saved binding as authorization to execute it.

After the mode and parameters are confirmed:

1. Check the local Telegram delivery configuration before any WEEX/Partner query:

   ```bash
   python -m weex_tg_bot config show
   ```

   Continue only when at least one configured Bot has a non-empty token and
   every selected push task has a non-empty profile and valid query. If the
   token, group, or task is missing, stop without querying Partner data and route
   the user through the GUI/CLI setup above.
2. For each distinct task, ask/use `$weex-partner-skill` for `get-commission`
   with that task's profile, UTC date, coin, scope, and each configured
   product type. Request `complete_list`; do not use a partial page or a summary
   that omits `fee`, `takerAmount`, `makerAmount`, or `sourceType`.
3. Combine the returned JSON envelopes as `{ "results": [ ... ] }` and pass them unchanged to this project:

   ```bash
   python -m weex_tg_bot send-result --date YYYY-MM-DD \
     --bot-name BOT_NAME --chat-id CHAT_ID --input partner-results.json
   ```

   `--input -` reads the same JSON from stdin.
4. Stop without sending if any envelope is not `ok=true`, `complete=true`, `partial=false`, or its records are not complete objects.

## Metric contract

- `Trading Volume`: `takerAmount + makerAmount`
- `Fee`: sum of `fee`
- `Commission`: sum of `commission`
- `Sub-affiliate Commission`: sum of `commission` where `sourceType == 2`
- `Final Income`: explicit configured formula, default `Commission - Sub-affiliate Commission`

Use Decimal arithmetic. Reject missing fields, invalid/negative amounts, unknown source types, mixed coins, and incomplete Partner results. Do not fill missing values with zero and do not silently skip records.

## Configuration and scheduling

- GUI: `python -m weex_tg_bot gui --language auto|<locale>`; it opens on three
  areas: Overview, Push tasks, and Help. Overview provides searchable Bot and
  standalone group catalog tables plus New/Edit/Delete actions. Bot dialogs own
  name, token, and Partner path; group dialogs own only group name and Chat ID.
  The Push tasks editor owns Bot/group target, profile, query, task language,
  query windows, push times, and IANA timezone, and the task list provides
  Telegram test and immediate-send actions.
- The GUI discovers locale JSON files from `weex_tg_bot/locales/`, detects the system
  locale at startup, and supports immediate switching from the header selector. The
  bundled locales are `en_us`, `zh_cn`, `zh_tw`, `ko`, `ja`, `vi`, `id`, `th`,
  `fa_ir`, `ar`, `tr`, `de`, `fr`, `it`, `es_es`, `pt_pt`, `pl`, `ru`, `uk`,
  `az`, `es_419`, `es_ar`, and `pt_br`; adding a locale JSON with the same keys is
  sufficient to extend the list. `--language <locale>` forces a language for a
  launch, while `--language auto` follows the operating-system locale. Arabic and
  Persian apply RTL text direction automatically. GUI labels and Telegram formatter
  copy are loaded from the same catalog, and each push task persists its language.
- GUI preflight/install: use `doctor --json` to decide whether the system is GUI-capable and expose `skill_root_candidates`; before either `gui-install` or `gui`, automatically persist a unique valid candidate from the current AI tool's skill roots, stop on ambiguity/missing candidates, then run `python -m weex_tg_bot gui-install --accept-managed-runtime` in the background when dependencies are missing, and finally launch `python -m weex_tg_bot gui --language auto`.
- CLI: `doctor`, `gui-preflight`, `gui-install`, `config set`, `config add-group`, `config add-task`, `config find`, `config remove-bot`, `config remove-group`, `config clear-token`, `config show`, `test-telegram`, `send`, `send-result`, and `run`. `config find bot [QUERY]` searches Bot names; `config find group [QUERY]` searches group names and Chat IDs. `send-result` always requires an explicit `--bot-name` and `--chat-id`; `run --once` executes every enabled task schedule immediately.
- Agent-assisted setup: offer to run the CLI configuration directly; require a
  custom Bot name, Bot token, standalone group name/Chat ID, and one or more
  independently named push tasks with profile/query. The token may come through
  GUI/stdin/environment, or directly in chat
  when the user explicitly authorizes that route. For chat-submitted tokens, use
  only stdin/environment and never repeat, log, or put the token in a command
  argument.
- Bot routing: one custom logical Bot name owns one token and any number of
  independent group associations and push tasks. Create the Bot first, then
  use `config add-group` or the GUI group dialog to create the standalone group
  catalog entry. The association is materialized when a push task selects the
  Bot and group; use `config add-task` or the GUI task page for profile/query/
  language/schedules. Both paths read and write the same SQLite tables, so a
  task created in either path is visible to the other.
  The SQLite database is the source of truth; there is no JSON migration path.
  The GUI Overview supports case-insensitive lookup by Bot name, group name, or
  Chat ID. Deleting a Bot removes its push tasks; deleting a standalone group
  removes every task targeting that Chat ID. The group catalog columns are limited
  to group name and Chat ID; profile, query, language, and schedules are task
  fields.
- Task query controls: derive coin/product suggestions from the confirmed
  official Partner field catalog at runtime, but do not enforce a local enum;
  pass user-entered values to the official Partner skill for validation. Load
  referral UID options only through the official list-referral-uids operation.
  UID search is local over the complete loaded result. When all-referrals is
  explicitly selected, disable and ignore the UID selector; never infer
  all-referrals from an empty UID list.
- Unattended mode: the GUI starts an in-process scheduler while it is open; headless hosts run `python -m weex_tg_bot run`. The project discovers the installed Partner CLI from `WEEX_PARTNER_CLI`, `WEEX_AGENT_SKILLS_ROOT`, or common Codex skill directories; `--skill-root` remains an explicit override. It checks each push task's schedules in that task's IANA timezone, computes the previous complete UTC natural period (or an anchored custom `Nd` window), queries due tasks, and sends once per `(task, period window)`. `run --once` executes all enabled task schedules. A manual `send` is not a substitute for the mode question: the agent must first obtain an explicit task selection or complete ad-hoc query parameters, then use an explicit target task.
- Delivery is idempotent per `(saved profile, UTC date, Bot name, Telegram chat ID)`. Use `--force` only for an intentional resend.

The project must remain fail-closed: query, aggregation, Telegram, or ledger failure means the delivery is not reported as successful.
