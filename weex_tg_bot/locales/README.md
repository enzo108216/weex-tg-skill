# Locale catalog

The JSON files in this directory are the single catalog for both the Tk GUI and
Telegram delivery text. The loader discovers them automatically; no Python
switch statement needs to be changed when adding a language.

The user-facing usage guides are available in [Chinese](../../README.md) and
[English](../../README.en.md). `telegram_push_copy.md` is the generated,
human-readable preview of the localized Telegram message for every bundled
locale.

To add a locale:

1. Copy `en_us.json` to `<normalized-locale>.json` (for example `nl.json` or
   `zh_hk.json`).
2. Keep every key and every `{placeholder}`; translate the values only.
3. Use lower-case BCP-47-style names with `_` (`pt_br`, not `pt-BR`).
4. Add the locale to the catalog test when it becomes a supported/bundled
   language, then run the unit tests.

The catalog also contains the GUI's `help_body`, validation messages, period
labels, and message labels. Keep those values aligned with the runtime contract:
push times use the task's IANA timezone, while Partner query windows are UTC;
custom `Nd` windows require a UTC start date.

`ar`, `fa`, `he`, and `ur` automatically use the GUI's RTL direction handling.
`language_name` is the name shown in diagnostics; the GUI selector uses the
locale filename as its stable value.
