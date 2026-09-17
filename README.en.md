# WEEX Daily Rebate → Telegram

This local Python application provides a Windows/macOS GUI and a CLI for other
environments. It reads complete Partner commission results through the official
`weex-partner-skill`, aggregates them safely, and delivers summaries to
Telegram. It owns Telegram configuration, aggregation, delivery, and
idempotency; it does not copy or modify the Partner skill's REST, Vault,
signing, or profile implementation.

Language: [简体中文](README.md) · English (this page) · [localized Telegram copy](telegram_push_copy.md)

## What is delivered

The summary contains five metrics:

- Trading Volume = `takerAmount + makerAmount`
- Fee = `sum(fee)`
- Commission = `sum(commission)`
- Sub-affiliate Commission = `sum(commission where sourceType == 2)`
- Final Income = `Commission - Sub-affiliate Commission` (the formula is shown and configurable)

The default coin is USDT and the date boundary is the UTC calendar day.
Missing fields, partial Partner results, query failures, mixed coins, and
unknown `sourceType` values fail closed and are never sent.

## CLI quick start

Run the preflight first. It reports GUI capability and read-only Partner skill
path candidates:

```bash
python -m weex_tg_bot doctor --json
```

Create a Bot. Keep the token out of command arguments and logs:

```bash
printf '%s\n' "$TELEGRAM_BOT_TOKEN" | python -m weex_tg_bot config set \
  --bot-name rebates --skill-root /path/to/weex-agent-skills --token-stdin
```

Groups and push tasks are separate records. A group stores only its Chat ID and
display name; a push task stores the Bot/group target, Partner profile, query,
language, and schedules. Use the GUI task editor, or use `config add-group` to
maintain the standalone group catalog before `config add-task` materializes the
Bot/group target:

```bash
python -m weex_tg_bot config add-group -1001234567890 --group-name "Rebates"
python -m weex_tg_bot config add-task -1001234567890 \
  --bot-name rebates --task-name "Daily rebates" --profile account-1 \
  --all-confirmed --schedule 09:00=1d --schedule 18:00=1w \
  --timezone Asia/Shanghai --language en_us

# Explicit UID scope and a custom anchored window
python -m weex_tg_bot config add-task -1001234567891 \
  --bot-name rebates --task-name "Operations" --profile account-2 \
  --uids 10001,10002 --product-types SPOT \
  --schedule 23:00=3d@2026-09-01
```

`config add-task` reads the standalone group catalog and materializes the
Bot/group association in the push task. The GUI task editor uses the same
SQLite records. `--timezone` controls the local push clock; query windows
remain UTC.
Supported natural windows are `1d`, `1w`, `1m`, and `1y`. A custom `Nd` window
must include an anchor date in UTC (`Nd@YYYY-MM-DD`). A task with no schedule is
manual-only.

Inspect or maintain the configuration:

```bash
python -m weex_tg_bot config show
python -m weex_tg_bot config find bot rebates
python -m weex_tg_bot config find group rebates
python -m weex_tg_bot config clear-token --bot-name rebates
python -m weex_tg_bot config remove-bot rebates
python -m weex_tg_bot config remove-group -1001234567890
python -m weex_tg_bot test-telegram --bot-name rebates --chat-id -1001234567890
```

The GUI overview supports case-insensitive lookup by Bot name, group name, or
Chat ID. Deleting a Bot also deletes its push tasks; deleting a standalone group
deletes every push task targeting that Chat ID. The group catalog shows only
group name and Chat ID; profile, query, and schedules belong to push tasks.

The GUI, CLI, and Skill share the same SQLite database rather than separate
configuration stores. Bot name/token/Partner path belong to the Bot record;
group name/Chat ID belong to the standalone group catalog; task name, Bot/group
target, profile, query, language, and schedules belong to push tasks. The GUI
task editor and `config add-task` both read the same group catalog, and CLI token
updates preserve tasks created in the GUI.

Before GUI installation or launch, the CLI searches the current AI tool's skill
roots (environment-provided `*_SKILLS_ROOT`, `CODEX_HOME`, Codex vendor skills,
and common tool directories) for
`weex-partner-skill/scripts/weex_partner_cli.py`. A single valid candidate is
stored automatically; multiple candidates stop and require a choice; no
candidate stops the GUI flow with an actionable error.

For a manual delivery, first select one configured task (or collect a complete
ad-hoc query contract). Then pass complete Partner envelopes to the explicit
Bot/Chat binding:

```bash
python -m weex_tg_bot send-result --date 2026-09-15 \
  --bot-name rebates --chat-id -1001234567890 --input partner-results.json
```

Do not infer “yesterday”, the first profile, all groups, or all referrals from
missing user input. `run` keeps scheduled tasks active on a headless host;
`run --once` executes all enabled schedules immediately. `--force` is required
for an intentional resend of an already recorded delivery.

## GUI and localization

The GUI opens on an information-first Overview, a Push tasks area, and Help.
The Overview manages searchable Bot and standalone group lists; Bot/group edits
are modal dialogs. The Push tasks area owns Bot/group target selection, profile,
query, language, schedules, Telegram testing, and immediate sending. While the
window is open it runs the in-process scheduler; closing the window stops it.
On a headless host, use `run` instead.

```bash
python -m weex_tg_bot gui-preflight --json
python -m weex_tg_bot gui-install --accept-managed-runtime  # skill discovery runs first
python -m weex_tg_bot gui --language auto
```

`auto` follows the operating-system locale. The bundled catalog currently
contains `en_us`, `zh_cn`, `zh_tw`, `ko`, `ja`, `vi`, `id`, `th`, `fa_ir`, `ar`,
`tr`, `de`, `fr`, `it`, `es_es`, `pt_pt`, `pl`, `ru`, `uk`, `az`, `es_419`,
`es_ar`, and `pt_br`. GUI labels and Telegram copy use the same JSON catalog;
each push task stores its own language. Arabic and Persian automatically use
right-to-left text direction. Add a locale by copying `en_us.json`, preserving
all keys and placeholders, and using a lower-case underscore locale name.

## Responsibility boundary

Use `$weex-partner-skill` for profile resolution and Partner queries. This skill
accepts only complete envelopes (`ok=true`, `complete=true`, `partial=false`),
performs Decimal aggregation, and sends the localized Telegram message. The
SQLite database is the runtime source of truth; the default file is
`~/Library/Application Support/weex-tg-skill/config.sqlite3` on macOS (the
platform configuration directory is used on Windows/Linux) with mode `600`.
Tokens are stored in that database by default and are masked by `config show`.

For the full routing and safety rules, see [SKILL.md](SKILL.md). The complete
localized message templates are in [telegram_push_copy.md](telegram_push_copy.md).
