---
name: weex-tg-skill
description: Push complete daily WEEX Partner rebate results to Telegram through a manual or scheduled workflow with custom Bot and group names. Use together with the installed weex-partner-skill; this skill owns Telegram configuration, aggregation, delivery, and idempotency, not WEEX REST access.
---

# WEEX Telegram Push Skill

This skill is installed alongside `weex-partner-skill` from the official `weex-agent-skills` project.

## Start here: AI-assisted installation and setup

For normal use, users should start from the AI tool rather than running the
Python modules manually. If this skill is not installed, recommend asking the
AI tool:

```text
Install the WEEX Telegram Push skill from
https://github.com/enzo108216/weex-tg-skill. Inspect the current setup, then
configure one scheduled Telegram push. Reuse existing records, ask only for
missing choices, keep secrets out of chat and logs, show a final summary, and
ask before any configuration write or message send.
```

After installation, short prompts such as these are sufficient:

```text
Use $weex-tg-skill to show my current Telegram push tasks.
```

```text
Use $weex-tg-skill to configure a daily 17:15 Asia/Shanghai push for the
existing rebate task.
```

Treat “one-click setup” as one conversational request, not permission to make
an unreviewed bulk change. The AI must still run the read-only preflight,
inspect current configuration, route WEEX profile and Partner questions to
their owning skills, show a final summary, and obtain confirmation immediately
before each configuration write. Testing Telegram or sending a real push is a
separate confirmation.

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

## Optional startup integration

Loading this skill is read-only. After loading, inspect the environment with
`python -m weex_tg_bot doctor --json` and inspect existing launch integration
with `python -m weex_tg_bot startup status`; do not start `run`, write a
system-startup entry, or create a desktop file merely because the skill was
discovered by an AI tool.

After an enabled scheduled task exists, offer one explicit startup choice at a
time:

- **User autostart**: `python -m weex_tg_bot startup install --target autostart --confirm`.
  This writes a user-level launch entry (macOS LaunchAgent, Windows Startup
  script, or Linux XDG autostart entry) that starts the headless `run` scheduler
  at the next login. It does not run the scheduler immediately.
- **Desktop launcher**: only when `doctor --json` reports `gui_capable=true`,
  use `python -m weex_tg_bot startup install --target desktop --confirm`.
  The generated launcher opens the GUI; the GUI scheduler runs while that
  window remains open only when it owns the shared scheduler lock. On a
  non-GUI host, route to user autostart instead.
- **No persistence**: leave the configuration saved and let the user start
  `python -m weex_tg_bot run` manually when desired.

The `--confirm` flag is mandatory for install/remove operations. Never silently
convert a skill load or a normal Telegram configuration write into a persistent
OS startup mutation. To remove an entry, require a separate confirmation and
run `python -m weex_tg_bot startup remove --target autostart --confirm` or the
same command with `--target desktop`. `startup status` is always safe to run
without confirmation.

The TG configuration GUI (`python -m weex_tg_bot gui --language auto`) is separate from the
WEEX account/profile manager supplied by `weex-trader-skill`. A request to open
the WEEX account manager follows that skill's GUI/runtime rules and does not
authorize TG configuration writes.

Use a short route question that makes the available choice and side effect
explicit, for example:

> Preflight result: desktop and Tkinter are available. Would you like to use the GUI, run the CLI yourself, or have the agent configure it step by step? The GUI path first discovers the Partner skill from the current AI tool and then handles the GUI runtime; the guided path first lists existing Bots, groups, and WEEX profiles and asks for only one choice or missing value at a time.

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

Before creating or changing any Bot, group, task, schedule, or Partner query,
resolve the delivery mode when the user has only said “send rebates to Telegram” (or an
equivalent ambiguous request). Ask one standalone question:

1. **Add a scheduled task**: save an independent task containing the Bot/group, profile, query, language, and schedule.
2. **One-time use**: execute one configured task or ad-hoc query without creating or changing a scheduled task.

Do not infer “add a task” from the existence of a schedule, a prior task, or a
general request to push. Do not query Partner, send Telegram, or write partial
configuration until the user chooses one mode. If the user explicitly says
“add a scheduled task” or “send once”, reuse that choice and continue. For single-use
delivery, follow the manual mode selection in section 5 and keep task storage
unchanged.

Run `python -m weex_tg_bot doctor --json` first. Present the GUI/CLI/agent route
and its side effect. A direct “configure/enable/repair” request authorizes the
configuration write, but not a test message unless the user asks for one. A GUI
choice authorizes the managed GUI runtime installation described above.

### Progressive prompting rules

The assistant must keep configuration conversational and incremental:

1. **Inspect before asking.** After the delivery mode is known, run `config show`/`config find` and read-only
   discovery first. Present existing Bots, groups, profiles, Partner products,
   and UID candidates when available; do not ask the user to retype known data.
2. **One decision per turn.** For task creation, ask for at most one selection or one missing value
   at a time: delivery mode → route → Bot → group → WEEX profile → query scope/products →
   language → schedule → final review → service startup method. If a value is already unambiguous and
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
 schedules, explain that the GUI and headless entry points share a cross-process
 scheduler lock. The GUI can stay open while `python -m weex_tg_bot run` (or an
 autostart entry) owns the scheduler; in that case the GUI skips its own
 scheduler. A second headless `run` exits without starting another loop.
 `run --once` executes all enabled schedule entries immediately.

### 6. Activate a scheduled task

After a task with one or more schedules is written and `config show` verifies it,
the task is **not active merely because it was saved**. Explain that a scheduler
service/process must be running for the schedule to take effect, then run the
read-only `doctor --json` and `startup status` checks again. Ask the user to
choose exactly one startup method based on those facts:

1. **Open the GUI now** (only when `gui_capable=true`): with explicit confirmation,
   launch `python -m weex_tg_bot gui --language auto`; the GUI scheduler runs
   while the window is open if no other scheduler owns the shared lock.
2. **Run automatically after login**: with explicit confirmation, install the user-level entry
   using `python -m weex_tg_bot startup install --target autostart --confirm`.
   It starts at the next login and does not start the scheduler immediately.
3. **Desktop launcher** (only when `gui_capable=true`): with explicit confirmation,
   run `python -m weex_tg_bot startup install --target desktop --confirm`, then
   tell the user to open the generated launcher. Creating the file does not
   launch the GUI.
4. **Run manually**: provide `python -m weex_tg_bot run`; only start it on the
   user's behalf after a separate explicit request to start the service now.
5. **Do not activate yet**: keep the task saved but clearly mark it inactive until a
   scheduler is started.

If the user chooses a startup method, complete that method in the same flow and
report its result/path. Never silently choose autostart, launch GUI, or start
`run` after task creation. If no schedule was saved, skip this activation step.

Explain these operational notes every time a scheduled task is activated:

- GUI, autostart, desktop launchers, and manual `run` share one cross-process
  scheduler lock. They may be used together: the first process that acquires
  the lock schedules, while GUI skips its scheduler and a second `run` exits
  cleanly. The lock is released automatically when the owner exits.
- Closing the GUI stops its scheduler. User autostart takes effect on the next
  login; installing it does not run now.
- `run --once` executes enabled schedules immediately and is not a harmless
  health check; treat it as an actual push and require separate confirmation.
- The saved profile and Partner environment still govern the data source; a
  test profile is not production data. Use `config show` and `startup status`
  when diagnosing a missed push.
- To disable a startup entry, use `startup remove --target ... --confirm`; to
  stop an already running manual service, stop that process (Ctrl-C/service
  manager) before removing its launcher.

If any Partner query, range segment, aggregation, Telegram send, or ledger write
fails, keep the operation fail-closed and report which binding/window was
affected. Never claim the whole push succeeded from a partial result.

### Telegram message template

Every delivered message must include the binding and query context before the
metrics so a reader can verify which account and scope produced the numbers:

```text
📊 WEEX Rebate Summary

Query Information
Trigger: Manual query
WEEX profile: <saved profile>
Scope: <all referrals (confirmed) or selected referral UIDs: ...>
Query time (UTC): <start> to <end>
Product types: <SPOT, FUTURES>
Settlement coin: <USDT/BTC>
Push target: <bot name> / <group name or chat id>

Results
Trading Volume: <amount> <coin>
Fee: <amount> <coin>
Commission: <amount> <coin>
Sub-affiliate Commission: <amount> <coin>
Final Income: <amount> <coin>

Formula: Final Income = Commission - Sub-affiliate Commission
Data status: complete
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

> Which configured Bot/group task would you like to execute, or would you like to run an ad-hoc query? For a configured task, I will first list the Bot name, group name, Chat ID, profile, and available schedules. For an ad-hoc query, provide the UTC start/end, profile, coin/products, scope (all referrals or a UID list), and target Bot/group.

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
- CLI: `doctor`, `gui-preflight`, `gui-install`, `config set`, `config add-group`, `config add-task`, `config find`, `config remove-bot`, `config remove-group`, `config clear-token`, `config show`, `test-telegram`, `send`, `send-result`, `run`, and `startup status|install|remove`. `config find bot [QUERY]` searches Bot names; `config find group [QUERY]` searches group names and Chat IDs. `send-result` always requires an explicit `--bot-name` and `--chat-id`; `run --once` executes every enabled task schedule immediately and must not be used as a silent startup probe.
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
- Unattended mode: the GUI and headless `python -m weex_tg_bot run` share a cross-process scheduler lock. The first owner schedules; a GUI with an occupied lock remains usable but skips its scheduler, and a second `run` exits cleanly. The project discovers the installed Partner CLI from `WEEX_PARTNER_CLI`, `WEEX_AGENT_SKILLS_ROOT`, or common Codex skill directories; `--skill-root` remains an explicit override. It checks each push task's schedules in that task's IANA timezone, computes the previous complete UTC natural period (or an anchored custom `Nd` window), queries due tasks, and sends once per `(task, period window)`. `run --once` executes all enabled task schedules. A manual `send` is not a substitute for the mode question: the agent must first obtain an explicit task selection or complete ad-hoc query parameters, then use an explicit target task.
- Delivery is idempotent per `(saved profile, UTC date, Bot name, Telegram chat ID)`. Use `--force` only for an intentional resend.

The project must remain fail-closed: query, aggregation, Telegram, or ledger failure means the delivery is not reported as successful.
