# WEEX Telegram Push User Guide

This guide covers the current GUI, CLI, scheduled-task, and startup behavior.
For Agent routing and safety rules, see [SKILL.md](../SKILL.md).

## 1. AI-first installation and configuration

The recommended path is to let a skills-capable AI tool install and configure
the skill in one natural-language request:

```text
Install the WEEX Telegram Push skill from
https://github.com/enzo108216/weex-tg-skill. Check what is already configured,
then help me set up a scheduled Telegram push. Reuse existing Bot, group, and
WEEX profile records; ask one missing choice at a time; keep secrets out of
chat and logs; show a final summary; and ask before writing or sending.
```

After installation, use short prompts for common tasks:

```text
Use $weex-tg-skill to list my current Bots, groups, and push tasks.
```

```text
Use $weex-tg-skill to configure a daily 17:15 Asia/Shanghai push for the
existing rebate task.
```

```text
Use $weex-tg-skill to open the GUI and help me configure the push task.
```

“One-click” means one conversational request, not an unchecked bulk write. The
AI still runs `doctor --json`, inspects `config show`, routes profile and
Partner questions to their owning skills, confirms the final Bot/group/profile/
query/schedule summary, and treats test sends and real pushes as separate
explicit actions.

## 2. Prerequisites and preflight

The project requires Python 3.10 or newer and an installed
`weex-partner-skill`. Start with the read-only preflight:

```bash
python -m weex_tg_bot doctor --json
```

Use `gui_capable` to decide whether the desktop GUI is available. The report
also lists discovered Partner skill roots and the managed GUI runtime status.
Do not install a system Tkinter package; use the managed runtime flow when the
GUI is selected.

## 3. Configure a Bot, group, and task

The configuration is stored in one SQLite database. A Bot owns its name, token,
and Partner skill root. A standalone group owns its display name and Chat ID.
A push task owns the Bot/group target, saved WEEX profile, query, language, and
zero or more schedules.

Create a Bot through stdin or an environment variable:

```bash
printf '%s\n' "$TELEGRAM_BOT_TOKEN" | python -m weex_tg_bot config set \
  --bot-name rebates \
  --skill-root /path/to/weex-agent-skills \
  --token-stdin
```

Create a group and task:

```bash
python -m weex_tg_bot config add-group -1001234567890 --group-name "Rebates"
python -m weex_tg_bot config add-task -1001234567890 \
  --bot-name rebates --task-name "Daily rebates" --profile account-1 \
  --all-confirmed --schedule 17:15=1d \
  --timezone Asia/Shanghai --language en_us
```

Use `--uids 10001,10002` instead of `--all-confirmed` for an explicit scope.
Use `--product-types SPOT` to restrict products. The supported formulas are
`commission_minus_subaffiliate_commission` and `commission`.

Scheduled windows are complete previous UTC periods:

- `1d`: previous UTC day
- `1w`: previous complete Monday–Sunday UTC week
- `1m`: previous complete UTC calendar month
- `1y`: previous complete UTC calendar year
- `Nd@YYYY-MM-DD`: anchored custom N-day cycle in UTC

The schedule clock uses the task's IANA timezone. Query windows remain UTC.

Inspect the result without exposing the token:

```bash
python -m weex_tg_bot config show
```

## 4. GUI workflow

Use the GUI when `doctor --json` reports `gui_capable=true`:

```bash
python -m weex_tg_bot gui-preflight --json
python -m weex_tg_bot gui-install --accept-managed-runtime
python -m weex_tg_bot gui --language auto
```

The GUI provides searchable Bot and group catalogs, task creation/editing,
schedule editing, Telegram connection testing, and immediate sending. GUI and
CLI changes are written to the same SQLite database.

The GUI also participates in the shared scheduler lock. If another scheduler
already owns the lock, the GUI still opens and edits configuration but its
background scheduler does not start.

## 5. Run scheduled tasks

On a headless host, or when you want a foreground scheduler, run:

```bash
python -m weex_tg_bot run
```

The process checks enabled schedules every 20 seconds. Only one scheduler
instance per configuration directory is allowed. GUI, autostart, desktop
launchers, and manual `run` may be used together:

- the first process to acquire the lock performs scheduling;
- a GUI whose lock is occupied stays usable but skips its scheduler;
- a second `run` prints `scheduler already active; not starting another scheduler`
  and exits successfully;
- the lock is released automatically when the owner exits or crashes.

`run --once` executes every enabled schedule immediately and is an actual push,
not a harmless health check. Treat it as a separate, explicitly confirmed
operation.

## 6. Startup integration

Inspect current startup files:

```bash
python -m weex_tg_bot startup status
```

Install login autostart:

```bash
python -m weex_tg_bot startup install --target autostart --confirm
```

On macOS this creates a user LaunchAgent; on Windows it creates a Startup
script; on Linux it creates an XDG autostart entry. Autostart takes effect at
the next login and does not immediately run the scheduler.

Install a desktop launcher on a GUI-capable host:

```bash
python -m weex_tg_bot startup install --target desktop --confirm
```

The launcher opens the GUI. Remove an entry only with an explicit confirmation:

```bash
python -m weex_tg_bot startup remove --target autostart --confirm
python -m weex_tg_bot startup remove --target desktop --confirm
```

## 7. Manual delivery and testing

For a manual push, explicitly select one configured task or provide a complete
ad-hoc query. Do not infer “yesterday”, the first profile, all groups, or all
referrals from missing input.

To send complete Partner envelopes to one target:

```bash
python -m weex_tg_bot send-result --date 2026-09-15 \
  --bot-name rebates --chat-id -1001234567890 --input partner-results.json
```

To test the Telegram connection, explicitly target the Bot and group:

```bash
python -m weex_tg_bot test-telegram \
  --bot-name rebates --chat-id -1001234567890
```

`--force` is required to resend an already recorded delivery. A test or manual
send is separate from starting the scheduler.

## 8. Storage, secrets, and responsibility boundaries

The default SQLite configuration is:

```text
~/Library/Application Support/weex-tg-skill/config.sqlite3
```

Windows and Linux use their platform configuration directories. The database
is created with mode `600`; `config show` masks Telegram tokens. Keep tokens out
of command arguments, logs, and source files.

Use `$weex-partner-skill` for WEEX profiles and Partner queries. This project
only accepts complete Partner results, aggregates them with Decimal arithmetic,
and delivers the localized Telegram message. It does not manage WEEX API keys,
Vault credentials, REST signing, or trading accounts.

For the localized message catalog, see
[telegram_push_copy.md](../telegram_push_copy.md).
