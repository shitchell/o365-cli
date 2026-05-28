# Changelog

## Unreleased — branch `ergonomics-2026-05-28`

A round of CLI ergonomics work aimed at making the tool intuitive for new
agents and scripts without workarounds. All changes are additive; existing
flag/subcommand spellings continue to work.

### Added

- **`chat search --context N`** — shows N messages immediately preceding
  each hit, for thread context. One extra Graph call per hit.
- **`chat.all` scope toggle + KQL-powered chat search.** Adds
  `ChannelMessage.Read.All` to the requested scopes when `chat.all = true`
  is set in `[scopes]`. With admin consent granted, `o365 chat search`
  uses Graph's server-side Search API instead of enumerating every chat
  locally — **52s → ~3s** in a Trinoor-sized tenant (~17× speedup). The
  query string accepts full KQL: wildcards (`release*`), boolean
  (`a OR b`, `a AND b`), phrase (`"client release"`), and property
  filters (`from:luke`, `sent>=2026-05-25`, `subject:"..."`). `--from`
  and `--since` are pushed into KQL automatically. Positional query is
  now optional — `o365 chat search --from "Luke" --since "1 week ago"`
  works without one. Search-API result shape is normalized to match the
  local format so display + JSON output don't care which path served the
  result.
- **SharePoint site drive enumeration** in `o365 files drives`. Once the
  tenant admin has granted `Sites.Read.All` / `Files.Read.All`, the
  default `files drives` still shows only personal + direct-membership
  drives (fast), but `-a`/`--all-sites` walks `/sites?search=*` and lists
  every accessible document library with the originating site name.
  `resolve_drive()` auto-falls-back to site enumeration if a name isn't
  found in the fast set, so `files list --drive "Engineering Team"`
  works without a separate discovery step.
- **Global `--json` flag** on every list/read/search/info command. Works
  in either position: `o365 --json mail read` or `o365 mail read --json`.
  Coverage: `mail read`, `mail search`, `chat list`, `chat read`,
  `chat search`, `files drives`, `files list`, `files search`,
  `calendar list`, `contacts list`, `contacts search`, `recordings list`,
  `recordings search`, `recordings info`, `auth status`.
- **`mail read -f "Sent Items"` works.** Mail folders can now be referred
  to by display name (Inbox, "Sent Items", Drafts, "Deleted Items",
  "Junk Email", Outbox, Archive, …) in addition to Graph well-known
  slugs and full folder IDs. Unknown names are looked up via
  `/me/mailFolders?$filter=displayName eq '…'`.
- **`chat read --chat <ID>`** as a flag-form alias for the positional
  chat ID. Mirrors `chat send --chat`.
- **Subcommand aliases**: `mail list` / `mail ls` → `mail read`,
  `calendar list-events` / `calendar events` → `calendar list`,
  `files ls` → `files list`, `recordings ls` → `recordings list`.
- **Resumable upload sessions for files ≥ 4 MB** in `files upload` and
  (transitively) `chat send -f`. Streams in 10 MiB chunks with per-chunk
  progress to stderr.
- **`get_access_token(refresh_if_expires_within=…, force_refresh=…)`** —
  the parameters that the function already implemented are now exposed.

### Changed

- **Chat display now decodes HTML entities.** All chat-message render
  paths (`chat read`, `chat search`, JSON serializers) now run
  `html.unescape()` after stripping tags, so `&nbsp;` / `&amp;` /
  `&quot;` etc. appear as their real characters instead of literal
  entity strings.
- **Search-snippet whitespace is collapsed.** The Graph Search API's
  `summary` field packs attachment filenames against body text with
  long runs of whitespace; `chat search` now collapses runs of 2+
  whitespace into a single space for display only.
- **`mail send` now sends via Microsoft Graph (`/me/sendMail`)** instead
  of shelling out to `python -m trinoor.email`. The SMTP credentials in
  `~/.env` are no longer required — the same OAuth token authenticates
  sends. The subparser now defines real flags (`-r`/`--recipient`,
  `-c`/`--cc`, `-b`/`--bcc`, `-S`/`--subject`, `-A`/`--attachment`,
  `-H`/`--html`, `-T`/`--text`, `--header`, `-f`/`--from`, `--no-save`),
  so `o365 mail send --help` is informative and argparse no longer
  rejects documented options with "unrecognized arguments". Attachments
  are inlined up to ~3 MB; larger ones go through a draft +
  `createUploadSession` + `send` flow automatically.
- **`chat list` shows stable, multi-member labels for unnamed group
  chats.** Previously the same chat could appear as "Lee Narisma" one
  run and "Erick Donque" the next because Graph's member ordering
  varied. Now renders as `Group(<n>): A, B, C [+N more]` with members
  sorted by name.
- **Top-level `--help`** reshuffled into "Common workflows" and
  "Scripting tips" sections that surface recent additions
  (folder-name resolution, `--chat`, `--json`, attachment sizes).

### Removed

- `mail send`'s dependency on the `trinoor.email` Python module. The
  package can be uninstalled if nothing else uses it.

### Notes

- Pre-existing test failure in `tests/test_mail.py::TestMailSync` references
  `o365.mail.MAIL_DIR` which doesn't exist (the constant is `MAILDIR_BASE`
  in current code). Not introduced by this branch; flagged for follow-up.
