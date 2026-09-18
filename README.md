# WEEX Daily Rebate → Telegram

Language: English (this page) · [简体中文](README.zh-CN.md) · [user guide](docs/user-guide.md)

This local Python application provides a Windows/macOS GUI and a CLI for other
environments. It reads complete Partner commission results through the official
`weex-partner-skill`, aggregates them safely, and sends summaries to Telegram.
It owns Telegram configuration, aggregation, delivery, and delivery idempotency;
it does not copy or modify the Partner skill's REST, Vault, signing, or profile
implementation.

The full end-user walkthrough is in the [user guide](docs/user-guide.md).
The [skill contract](SKILL.md) contains the routing and safety rules used by
Codex. The localized Telegram message catalog is in
[telegram_push_copy.md](telegram_push_copy.md).

## What is delivered

The summary contains five metrics:

- Trading Volume = `takerAmount + makerAmount`
- Fee = `sum(fee)`
- Commission = `sum(commission)`
- Sub-affiliate Commission = `sum(commission where sourceType == 2)`
- Final Income = `Commission - Sub-affiliate Commission`

The default settlement coin is USDT and scheduled windows use complete UTC
calendar periods. Missing fields, partial Partner results, query failures,
mixed coins, and unknown `sourceType` values fail closed and are never sent.

## Start here with AI

For normal use, you do not need to run the Python commands yourself. In a
skills-capable AI tool, ask:

```text
Install the WEEX Telegram Push skill from
https://github.com/weex-labs/weex-tg-skill. Check the current setup, then
configure one scheduled Telegram push for me. Reuse existing Bot, group, and
WEEX profile records when possible; ask only for missing choices, keep tokens
out of chat and logs, show me a final summary, and ask before writing or
sending anything.
```

After installation, simple requests can be phrased naturally:

```text
Use $weex-tg-skill to show my current Telegram Bots, groups, and push tasks.
```

```text
Use $weex-tg-skill to configure a daily 17:15 Asia/Shanghai push for the
existing rebate task. Ask me only for values that are missing.
```

```text
Use $weex-tg-skill to open the GUI and help me configure the Telegram push.
```

The AI still performs a read-only preflight, checks existing configuration,
routes WEEX profile/Partner questions to their owning skills, and confirms the
final configuration before a write. A test message or an actual push always
requires a separate explicit request.

## Quick start

Run the read-only preflight first:

```bash
python -m weex_tg_bot doctor --json
```

Create a Bot without putting its token in command arguments or logs:

```bash
printf '%s\n' "$TELEGRAM_BOT_TOKEN" | python -m weex_tg_bot config set \
  --bot-name rebates \
  --skill-root /path/to/weex-agent-skills \
  --token-stdin
```

Create a standalone group and a scheduled push task:

```bash
python -m weex_tg_bot config add-group -1001234567890 --group-name "Rebates"
python -m weex_tg_bot config add-task -1001234567890 \
  --bot-name rebates --task-name "Daily rebates" --profile account-1 \
  --all-confirmed --schedule 17:15=1d \
  --timezone Asia/Shanghai --language en_us
```

`--timezone` controls the push clock; query windows remain UTC. Supported
natural windows are `1d`, `1w`, `1m`, and `1y`. A custom `Nd` window must use
an anchored UTC date, for example `23:00=3d@2026-09-01`. A task without a
schedule is manual-only.

Inspect the saved configuration:

```bash
python -m weex_tg_bot config show
```

For a complete configuration flow, manual delivery flow, GUI setup, and
troubleshooting, see the [user guide](docs/user-guide.md).

## GUI and scheduler modes

The GUI and CLI use the same SQLite configuration database. The GUI provides
Bot, group, task, language, schedule, Telegram test, and immediate-send flows:

```bash
python -m weex_tg_bot gui-preflight --json
python -m weex_tg_bot gui-install --accept-managed-runtime
python -m weex_tg_bot gui --language auto
```

For unattended operation, run:

```bash
python -m weex_tg_bot run
```

GUI, autostart, desktop launchers, and manual `run` share one cross-process
scheduler lock. The first process that acquires it performs scheduling. If a
headless scheduler already owns the lock, the GUI stays usable but skips its
own scheduler; a second `run` exits without starting another loop. The lock is
released automatically when the owner exits. `run --once` is an actual
immediate push, not a health check.

## Startup integration

Inspect or install user-level startup integration explicitly:

```bash
python -m weex_tg_bot startup status
python -m weex_tg_bot startup install --target autostart --confirm
python -m weex_tg_bot startup install --target desktop --confirm  # GUI-capable hosts only
python -m weex_tg_bot startup remove --target autostart --confirm
```

Autostart begins on the next login and does not run the scheduler immediately.
The desktop launcher opens the GUI. Both routes use the shared scheduler lock,
so they can coexist safely with another entry point.

## Storage and responsibility boundary

SQLite is the runtime source of truth. On macOS the default configuration is
`~/Library/Application Support/weex-tg-skill/config.sqlite3`; platform-specific
configuration directories are used on Windows and Linux. The database is
created with mode `600`, and Telegram tokens are stored there by default and
masked by `config show`.

Use `$weex-partner-skill` for profile resolution and Partner queries. This skill
accepts only complete Partner envelopes (`ok=true`, `complete=true`,
`partial=false`), performs Decimal aggregation, and sends the localized
Telegram message. It does not own WEEX account credentials or REST signing.
