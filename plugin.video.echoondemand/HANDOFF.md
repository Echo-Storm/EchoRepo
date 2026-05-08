# Echo OnDemand — Developer Handoff Notes

**Handed off at:** v3.0.0
**Status:** Stable; v3.0.0 changes (Live category, rename, settings backup/restore, icon refresh) are new in this release and untested in production at handoff time.

This document is for whoever picks this up next — including future-me. It covers what the code is doing, why specific decisions were made, what was deliberately left out, and what the natural next steps are.

---

## Current State

The addon works reliably on Kodi 21 Omega (Windows). v2.5.0 was tested in production with Real-Debrid for IPTV and Wrestling Rewind. v2.6.0 added Wrestling on Demand (WOD) and Fights on Demand (FOD). v3.0.0 adds a Live category, renames Wrestling → Wrestling Rewind for clearer labelling, refreshes the icon set with template-style additions, and introduces a Backup/Restore Settings safety net for users who fully uninstall before reinstalling.

All four MicroJen-format sources (WR, WOD, FOD, Live) share the same parser, debrid resolver, and link normaliser. The only differences are the feed root URLs and the menu structure used to walk into them.

**What works:**
- Movies and Series via Xtream Codes, including genre icons, TMDB backdrop caching, pre-buffer, context menus
- Wrestling Rewind navigation — full directory tree, sub-feeds, PPV feeds (4-pass parser handles structural quirks)
- Wrestling on Demand — curated tree (`STATIC_MENUS['wod_root']`) covering WWE/AEW/TNA/NWA/NJPW/ROH/RPW/Indy plus documentaries, interviews, special matches, archive
- Fights on Demand — curated tree (`STATIC_MENUS['fod_root']`) covering UFC events, MMA, Boxing, plus a Free / No Debrid sub-menu
- Live — `STATIC_MENUS['live_root']` currently has Live Wrestling (WOD live.xml). Parent menu in place for future sources.
- Debrid resolution — magnet URIs and HTTP hosters
- Cache system — all content types, with TMDB cache preserved across Refresh
- Settings backup/restore via JSON snapshot to `special://userdata/echoondemand_settings.json`
- Icon set — 50+ template-style PNGs covering all curated menu entries that have a natural label match

**What was deliberately excluded:**
- Live streams in WR or FOD — both are replay-only services upstream
- yt-dlp / additional resolver paths — resolveurl plus the 3-pass fallback in `resolve_best_link()` covers the hoster mix in practice
- NFL Rewind from the previous Echo Sports addon — same hosting domain, same MicroJen format, would be a 5-line addition (Pattern A) but not asked for in v3.0
- Trakt integration
- Server URL in settings — hardcoded by design for this user base
- Per-source feed root URL settings — stable enough that one-line code edits are simpler than user-facing settings
- Symbol-only icons (no logo reproductions). All new icons are text-on-template using existing addon artwork as the base.

---

## Key Design Decisions (3.0.0)

### Why rename, not consolidate

v3.0.0 went with renaming "Wrestling" → "Wrestling Rewind" rather than consolidating WR + WOD under a single "Wrestling" parent menu. Consolidation would have:
- Saved one entry from the root menu
- Cost one click for every wrestling-replay session

Renaming:
- Keeps each source one click from root, matching how Movies and Series sit at the root level
- Uses honest source labels (WR is the upstream service's actual name)
- Makes the root menu's structure mirror the upstream reality (three independent providers, not one with sub-providers)

If consolidation is later wanted, it's a 5-line `STATIC_MENUS` edit:
1. Add a `'wrestling_root'` entry referencing both WR and WOD
2. Replace the two root entries with a single one pointing at `wrestling_root`

### Why the Live category has a parent menu instead of a single root entry

Currently the Live menu has only one item (Live Wrestling). A single-entry sub-menu costs one click for nothing.

The trade-off: when (if) live fight feeds appear upstream, adding them is a one-line `STATIC_MENUS` edit instead of a code change involving routing, list_root, and possibly schema migrations. The parent menu is cheap to keep and cheap to grow.

If the parent never grows, it can be flattened in a later release with no functional change.

### Why STATIC_MENUS for the Live category despite single source

Same logic as WOD/FOD: the dispatch model is a uniform mechanism. Adding a one-off code path for "Live → just open this URL directly" would have introduced a special case that needs to be remembered when adding the next live source. Going through `STATIC_MENUS` keeps the rule simple: any curated tree, no matter how small, lives in `STATIC_MENUS`.

### Why Backup/Restore writes outside the addon's userdata directory

Kodi's per-addon userdata layout:
```
<KODI_HOME>/userdata/
  addon_data/
    plugin.video.echoondemand/    ← cleaned up on addon Uninstall
```

If the backup file lived inside `addon_data/plugin.video.echoondemand/`, an Uninstall would wipe it along with everything else — defeating the point.

`special://userdata/` resolves to `<KODI_HOME>/userdata/` itself, one level up from the addon's userdata. Files there survive any single-addon uninstall. Only a wholesale Kodi reset clears them.

The path is platform-portable (`xbmcvfs.translatePath` does the right thing on every platform Kodi runs on), so this is a clean cross-platform location.

### Why Backup is unconditional but Restore is gated by yes/no

Backup overwrites a file the user already chose to maintain — there's nothing to lose by re-running it. The notification confirms it ran.

Restore overwrites the user's currently-loaded settings — possibly with very stale credentials, possibly with the wrong account if they share the addon between profiles. A confirm-before-clobber dialog is the cheapest possible safety net.

The version guard on Restore is for the rarer case where a backup file from a future addon version is loaded into an older one. The `version` field jumps when the schema changes incompatibly. `_BACKUP_VERSION` starts at 1; any change that adds new keys can leave it alone (older versions just won't see the new keys), but a key rename or removal would bump to 2 and reject older readers.

### Why icon generation matched the existing template

The existing 40 icons all share the same artwork (target/dot graphic + red band) with only the bottom-band label text varying. New icons are produced by:
1. Loading an existing icon as a base (Action.png chosen for its high-quality template)
2. Refilling the bottom band's pixel region with the same red colour (`RGB(229, 57, 53)`)
3. Drawing the new label text in white DejaVuSans-Bold with auto-fit sizing (single-line for short labels, two-line for longer ones, matching the existing "WWE RAW" / "UFC REPLAYS" pattern)

This guarantees every new icon is visually indistinguishable from the existing set except for the label text. The generator script is reproducible (any time a new icon is needed, the same approach works).

The blank-template `Wrestling.png` (1684 bytes) was a placeholder from earlier development; it's been replaced with a proper "WRESTLING" icon in the same style.

---

## The Wrestling XML Parser — What Was Actually Happening (unchanged from 2.5.0)

Worth re-stating because everything in v3.0 still depends on it.

**Feed structure:**
- Feeds begin with `<?xml ...?>` processing instructions AND a `<layoutype>Z3R0</layoutype>` (or `<layouttype>`) obfuscation block. Both must be stripped before ET can parse the document.
- The close tag on `layouttype` has a deliberate typo: `</layoutype>`. The regex must match both for both open and close tags.
- Most feeds have multiple top-level `<xml>` elements (technically invalid XML). These must be wrapped in a synthetic `<root>` element for ET.
- Some feeds use a different wrapper element name than `<xml>`. The wrapper detection in `_collect_items` is now generic.
- Sublinks are sometimes direct children of `<item>`, sometimes nested inside a `<link>` child. Two-pass extraction handles both.
- Some items have genuinely malformed XML (unescaped `<` or `>` in torrent `dn` parameters). Pass 4 uses per-item regex extraction to recover all valid items when the full document parse fails.

**The four parse passes:**
1. Strip preamble, parse as-is
2. Strip preamble + escape bare `&`
3. Pass 2 + wrap in `<root>`
4. Per-item regex extraction

**The link format:**
Feeds append human-readable labels to URLs in parentheses: `https://host.com/file.mkv(Non Debrid)`. These must be stripped before resolveurl sees them. The regex covers both `http(s)://` and `magnet:` schemes.

**WOD/FOD/Live quirks (added in 2.6.0+, all still active in 3.0.0):**
- WOD feeds may use `<summaru>` instead of `<summary>` (deliberate typo). Aliased at parse time.
- WOD/FOD/Live titles may contain Kodi BBCode-style format tags including malformed variants. `strip_format_tags()` cleans these for display.

---

## Known Limitations

**Live category is single-source.** Only WOD has a live feed (`live.xml`). FOD is a replay-only service; WR has no live content. The parent menu is in place anticipating future sources.

**The server URL is hardcoded.** `SERVER = 'https://blueonesuperoceanhere.com'` in `default.py`. Single-line edit if it ever changes.

**WOD and FOD feed root URLs are hardcoded.** `WOD_BASE` and `FOD_BASE` constants at the top of `default.py`, with individual feed paths in `STATIC_MENUS`. One-entry edits per affected feed if anything moves upstream.

**Backup/Restore captures only the four user-facing settings.** No cache, no TMDB fanart, no per-feed cached state. This is deliberate — the backup is for credentials and per-user preferences, not for restoring an entire installation. If a "full backup" is ever needed, it's a `_BACKUP_KEYS` extension plus copying the addon profile dir.

**Backup file is plain JSON, including the password in cleartext.** No encryption. The file lives in Kodi's userdata directory, which is generally accessible only to the user account that runs Kodi. If the user's threat model requires encryption at rest for the password, the backup feature isn't the right tool — they should rely on Kodi's built-in settings.xml (also cleartext but inside Kodi's normal userdata tree).

**STATIC_MENUS does not validate menu_key references at load time.** A typo pointing at a non-existent sub-menu is only caught when the user clicks it. A startup-time validation pass exists in the test suite (test 9 in the regression set) but isn't run at addon startup.

**Wrestling feed cache uses URL-based filenames.** Sanitisation could collide for two different 120+ char URLs that differ only in non-alphanumeric characters. Very unlikely in practice.

**No retry logic on network failure.** Manual retry (re-open the folder) is the expected behaviour.

**`strip_format_tags()` may not catch every malformed BBCode variant.** Targets the patterns observed in real feeds. New shapes can be added with a regex widening; the function lives in `wrestling.py` next to the other text helpers.

---

## Natural Next Steps

In rough order of effort.

### 1. NFL Rewind (low effort)

Same hosting domain as WR (mylostsoulspace.co.uk). Same MicroJen format. Pattern A: master menu XML at `https://mylostsoulspace.co.uk/NFLRewind/xmls/MainXml/nflrewind-main.xml`. Add a single root entry pointing `mode=wr_list` at it. Done.

The previous Echo Sports addon had this. Some 23/24 season entries had dead URLs but recent seasons worked.

### 2. Per-source feed root URL settings (low effort)

The Wrestling Rewind side already reads `wr_root_url` from settings (just not exposed in settings.xml). Mirror that pattern for `wod_base` and `fod_base`. ~10 lines.

### 3. Live fights or live sports (low-medium effort)

When/if live fight feeds appear, add `live_fights` to `STATIC_MENUS['live_root']`. The single-source Live menu becomes a real category. Already designed for this.

### 4. Consolidate replay sources (cosmetic, reversible)

If the root menu ever feels crowded, fold WR + WOD + FOD under a "Replays" parent menu. Two `STATIC_MENUS` entries plus removing two root entries plus adding one. ~10 lines.

### 5. Encrypt the Backup file (medium effort)

If the cleartext password concern matters, AES-encrypt the snapshot using a key derived from a user-set passphrase. Adds a settings field, a new dialog flow, and a dependency on `cryptography` or similar. Worth the effort only if the threat model demands it.

### 6. Wider `strip_format_tags()` coverage (low effort, reactive)

If/when a feed surfaces a malformed BBCode tag the current regex doesn't catch, widen the regex and add a unit test. Lives in `wrestling.py`.

### 7. Per-skin themes for the icon set (low effort, cosmetic)

Currently icons are fixed at white-on-red-band over the dark template. A future skin variant (e.g., light theme) would need a parallel set. The generator script in the AUDIT_NOTES.md / commit history can be re-run with different colour parameters.

---

## Code Health

The codebase is in good shape as of v3.0.0. There is no dead code, no disabled features, no commented-out blocks. Every function does one thing.

The v3.0 changes were scope-controlled:
- No new dependencies beyond what was already present
- No new third-party modules
- No new resolver paths
- No skin XML changes — `Container.Content(files)` suppression is unchanged for all WR/WOD/FOD/Live views

The wrestling.py changes from v2.6.0 are still purely additive (one tag alias, one new utility function). The default.py changes in v3.0.0 add:
- Two new functions (`do_settings_backup`, `do_settings_restore`) plus a small helper (`_backup_path`)
- One new menu key in `STATIC_MENUS` (`live_root`)
- Three new root entries (Live, Backup Settings, Restore Settings)
- Two new router branches (`settings_backup`, `settings_restore`)
- Updated `icon_label` fields on existing `STATIC_MENUS` entries to point at the new bundled icons
- The Wrestling → Wrestling Rewind label change in `list_root`

None of these regress existing behaviour. URL formats are preserved (the Wrestling Rewind entry still uses `mode=wr_list` against the same XML) so no existing bookmarks or context-menu deeplinks break.

The main ongoing risk is the upstream feeds. They are third-party external services with no SLA. If `mylostsoulspace.co.uk` or `l3grthu.com` go offline or change their XML structure significantly, the affected sections will stop working. The fallback path (pass 4 per-item extraction) buys a lot of resilience against structural changes; a completely different feed format would require parser updates.

Feed URLs are soft-coded:
- Wrestling Rewind: one constant in `default.py`, readable from settings if `wr_root_url` is set
- Wrestling on Demand: `WOD_BASE` constant + `STATIC_MENUS['wod_*']` paths
- Fights on Demand: `FOD_BASE` constant + `STATIC_MENUS['fod_*']` paths
- Live: `STATIC_MENUS['live_root']` paths

Pointing at a mirror is an edit to a handful of lines.

---

## File Checksums (v3.0.0)

For verifying a clean install:

```
default.py        ~1750 lines, ~70KB
wrestling.py      ~700 lines, ~26KB
settings.xml      4 settings (unchanged from 2.5.0)
addon.xml         resolveurl as hard import (unchanged from 2.5.0)
README.md         this file's companion
HANDOFF.md        this file
icons             50+ template-style PNGs in resources/images/genres/
```
