# Echo OnDemand — Developer Handoff Notes

**Handed off at:** v2.6.0
**Status:** Stable; WOD/FOD integration is new in this release and untested in production at handoff time.

This document is for whoever picks this up next — including future-me. It covers what the code is doing, why specific decisions were made, what was deliberately left out, and what the natural next steps are.

---

## Current State

The addon works reliably on Kodi 21 Omega (Windows). v2.5.0 was tested in production with Real-Debrid for IPTV and Wrestling Rewind. v2.6.0 adds Wrestling on Demand (WOD) and Fights on Demand (FOD) using the same MicroJen feed format that Wrestling Rewind uses, so the same parser, debrid resolver, and link normaliser cover all three sources.

**What works:**
- Movies and Series via Xtream Codes, including genre icons, TMDB backdrop caching, pre-buffer, context menus
- Wrestling Rewind navigation — full directory tree, sub-feeds, PPV feeds (which had structural XML issues now handled by a 4-pass parser)
- Wrestling on Demand — curated category tree (`STATIC_MENUS['wod_root']`) covering WWE/AEW/TNA/NWA/NJPW/ROH/RPW/Indy plus documentaries, interviews, special matches, archive
- Fights on Demand — curated category tree (`STATIC_MENUS['fod_root']`) covering UFC events, MMA, Boxing, plus a Free / No Debrid sub-menu
- Debrid resolution — magnet URIs and HTTP hosters, with proper label stripping and ResolvedURL object handling
- Cache system — all content types, including MicroJen feeds in the profile directory, with TMDB cache preserved across Refresh
- Clean navigation history — Refresh/Clear Cache does not pollute the back stack

**What was deliberately excluded:**
- Live streams from any source — Echo OnDemand is on-demand by design
- Trakt integration (removed from Wrestling Rewind source, never added to IPTV side)
- Server URL in settings — hardcoded by design for this user base
- Wrestling-specific settings — TTL is fixed at 30 min, root URLs are hardcoded with one-line change points
- yt-dlp integration from the previous Echo Sports addon — resolveurl + the 3-pass fallback in `resolve_best_link()` is sufficient for the hoster mix WOD and FOD use

---

## Key Design Decisions

### Why one wrestling.py serves three sources

WR, WOD, and FOD all use the MicroJen XML format. The 4-pass parser, the bare-`&` escaper, the label-suffix stripper, the URI scheme validator, and the debrid-first resolution chain all apply equally to each source. Forking a separate parser per source would duplicate code that's already been hardened against the format's quirks.

The `<summaru>` typo alias added in v2.6.0 is a WOD-specific concession but was implemented in the shared parser because (a) it's harmless for the other sources and (b) keeping a single parser is more valuable than purity.

### Why STATIC_MENUS for WOD and FOD instead of pointing at upstream menu XMLs

WOD's host (`l3grthu.com/hades/wod21/`) does not serve a master menu XML — there's no equivalent of Wrestling Rewind's `wrestlingrewind-main.xml`. The previous Echo Sports addon worked around this by hardcoding a category tree in Python.

FOD's host (`mylostsoulspace.co.uk/FightsOnDemand/`) does have a `fodmain-new.xml` master menu, but its labels carry BBCode noise like `[COLOR lime]Latest UFC/MMA[/COLOR]` and `[COLOR cyan]Free (No Debrid)[/COLOR]`. A curated tree gives a clean, predictable display that's not at the mercy of upstream label edits.

For consistency, both sources use the same `STATIC_MENUS` mechanism. Adding or removing a feed is a one-entry edit in pure Python data — no view code or routing changes required.

### Why the root menu was not nested

A top-level "Replays" submenu containing Wrestling, WOD, and FOD would reduce the root menu by two entries but add a click between the user and every replay session. Three flat root entries cost almost nothing visually and save a click every time. The user is also expected — Movies / Series / Wrestling / Wrestling on Demand / Fights on Demand / Refresh — fits comfortably in any skin.

### Why `setContent('files')` for category and replay views (unchanged from 2.5.0)

This is the single most important thing to understand about the skin behaviour. Aeon Nox Silvo renders a large info panel on the right side for `movies`, `tvshows`, and `videos` content. For category lists (genre folders) and replay items (where the per-item summary is already shown via the Info button), this panel either shows nothing or shows the genre icon scaled up in an ugly way.

`setContent('files')` tells the skin "this is a generic file browser, not a media library view" — the right panel is suppressed. The companion skin XML changes (MyVideoNav.xml, View_50_List.xml) reinforce this with explicit `Container.Content(files)` conditions.

In v2.6.0 the WOD and FOD list_wr code path now sets a Plot via InfoTagVideo when an item has a summary. This does NOT bring the right panel back — the suppression depends on `Container.Content(files)`. The Plot only surfaces when the user presses the Info button, which is the desired behaviour.

If the skin is ever replaced or updated, audit the `setContent()` value for each view and check what the skin does with it.

### Why `script.module.resolveurl` is a hard dependency

Everyone who uses this addon has Real-Debrid configured. Making resolveurl optional would require adding a toggle in settings and building a path that tries direct play for everything — that path exists as a fallback in `resolve_best_link()` anyway, but the UX assumption throughout is that debrid works. FOD provides a Free / No Debrid sub-menu for users without one, but even those streams resolve cleaner with resolveurl available because some still go through hoster pages.

### Why `base64 JSON` encoding for replay play items (unchanged from 2.5.0)

Items can have a list of sublinks (multiple candidate URLs). Passing a list through a URL parameter cleanly requires some form of serialisation. Base64-encoded JSON is the approach Wrestling Rewind's own code uses internally — it's compact, round-trips without encoding issues, and keeps `play_wr()` self-contained. The alternative would be per-field URL params, which breaks for list-typed fields.

This applies equally to WOD and FOD; all three sources use the same play_wr.

### Why TMDB cache is preserved across Refresh in 2.6.0

`tmdb_fanart.json` accumulates over many movie plays — each unique `name|year` is one TMDB API call. The previous behaviour (delete it with everything else on Refresh) meant a single cache clear undid hours of accumulated lookups, and the user had to play each movie again before fanart returned. Preserving it costs nothing (the file is small even after thousands of plays) and matches the user's mental model: "Refresh" should refresh listings, not nuke art.

If the TMDB cache itself needs clearing (e.g., a stale URL got cached), it can be deleted manually from the profile directory.

---

## The Wrestling XML Parser — What Was Actually Happening (unchanged from 2.5.0)

This took several rounds of live debugging to get right. Worth documenting clearly.

**The WR feed structure:**
- Feeds begin with `<?xml ...?>` processing instructions AND a `<layoutype>Z3R0</layoutype>` (or `<layouttype>`) obfuscation block. Both must be stripped before ET can parse the document.
- The close tag on `layouttype` has a deliberate typo: `</layoutype>`. The regex must match both `layouttype` and `layoutype` for both open and close tags.
- Most feeds have multiple top-level `<xml>` elements (technically invalid XML — more than one root element). These must be wrapped in a synthetic `<root>` element for ET.
- Some feeds (the PPV feed specifically) use a different wrapper element name than `<xml>`. The original code only checked for `<xml>` as a wrapper, silently returning nothing for PPV content.
- Sublinks are sometimes direct children of `<item>`, sometimes nested inside a `<link>` child. A flat loop misses the nested case. The fix: `element.findall('.//sublink')` after the flat pass, identical to WR's own parser.
- Some items in some feeds have genuinely malformed XML (unescaped `<` or `>` in torrent `dn` parameters). Pass 4 uses per-item regex extraction to recover all valid items when the full document parse fails.

**The four parse passes:**
1. Strip preamble, parse as-is
2. Strip preamble + escape bare `&` (not already-escaped entities)
3. Pass 2 + wrap in `<root>` (handles multiple top-level elements)
4. Per-item regex extraction — one malformed item is skipped, rest succeed

**The link format:**
Feeds append human-readable labels to link URLs in parentheses: `https://host.com/file.mkv(Non Debrid)`. These must be stripped. The original stripping code only accepted `http` prefixes — magnet links (which start `magnet:`) had their labels NOT stripped, so resolveurl received broken magnet URIs. Fixed in v2.3.

**WOD-specific quirks (new in v2.6.0):**
- Some WOD feeds use `<summaru>` instead of `<summary>` (deliberate typo). The parser aliases it.
- WOD/FOD titles often contain Kodi BBCode-style format tags including malformed variants (`[COLORwhite]` with no space). `strip_format_tags()` in `wrestling.py` cleans these for display.

---

## Known Limitations

**The server URL is hardcoded.** `SERVER = 'https://blueonesuperoceanhere.com'` in `default.py`. This is a deliberate choice for this deployment, not an oversight. If the server changes, it's a one-line edit. If a settings UI is needed, add `<setting id="server_url" .../>` to settings.xml, read it in `get_credentials()`, and update `play_movie()` and `play_episode()` to use the setting.

**WOD and FOD feed root URLs are hardcoded.** `WOD_BASE` and `FOD_BASE` are constants at the top of `default.py`, and individual feed paths live in `STATIC_MENUS`. If a feed URL changes upstream, it's a one-entry edit per affected feed. This is consistent with the "soft-coded with one change point" pattern used for Wrestling Rewind.

**WOD has no live coverage.** Deliberate per-product scope (Echo OnDemand is replays only). The upstream `live.xml` feed exists but is not wired up. If live ever becomes desirable, add `wod_live` to STATIC_MENUS pointing at `WOD_BASE + '/live.xml'` and a root entry that drills into it.

**STATIC_MENUS does not validate at load time.** A typo in a `menu_key` (pointing at a non-existent sub-menu) is only caught when the user clicks it; `list_static_menu` shows a "Menu not found" notification and ends the directory cleanly. A startup-time validation pass (recurse through every menu_key and confirm targets exist) could be added if menu count grows.

**Wrestling feed cache uses URL-based filenames.** `_cache_filename()` sanitises the URL to produce a filename. If two URLs somehow sanitise to the same string (very unlikely in practice — would need 120+ character URLs that differ only in non-alphanumeric characters), there would be a collision. Not worth fixing unless it actually happens.

**No retry logic on network failure.** If the IPTV API or any MicroJen feed returns a network error, the user sees a dialog and the directory fails. There is no automatic retry. For a hobbyist addon this is fine — manual retry (re-open the folder) is the expected behaviour.

**`strip_format_tags()` may not catch every malformed BBCode variant.** It targets the patterns observed in real WOD/FOD feeds (`[COLOR x]`, `[COLOR ]`, `[COLORx]`, `[COLOR #FF00FF]`, `[B]`, `[I]`, `[CR]`, `[UPPERCASE]`, `[LOWERCASE]`, plus closing variants). New malformed shapes will pass through and display literally. The regex can be widened with no fallback risk.

---

## Natural Next Steps

These are the things that logically come next, in rough order of effort:

### 1. Per-source feed root URL settings (low effort)

Add `wr_root_url`, `wod_base`, `fod_base` as settings. The Wrestling Rewind side already reads `wr_root_url` from settings (it just doesn't appear in settings.xml). Mirror that pattern for WOD and FOD bases. Ten lines, no new modules. Useful only if upstream URLs change frequently — currently they're stable.

### 2. WOD live channels (low-medium effort)

If desired, add `wod_live` to STATIC_MENUS pointing at `WOD_BASE + '/live.xml'` and add a root entry. The existing parser will handle the feed (live items are MicroJen items just like any other). Whether streams play depends on what hosters/CDNs the live feeds use; resolveurl coverage may vary.

### 3. NFL Rewind / other mylostsoulspace sources (medium effort)

The previous Echo Sports addon also had NFL Rewind via the same hosting domain. Same MicroJen format. Could be added as a fourth replay section using the same Pattern A or B from the README. NFL Rewind has a master menu XML so Pattern A applies — root entry, `mode=wr_list` against the master XML, done in 5 lines.

### 4. Consolidate replay sources under one root entry (cosmetic)

If the root menu starts feeling crowded, the three replay sources could be folded into a single "Replays" entry that opens a sub-menu. This is a `STATIC_MENUS` change and one fewer root entry. Trade-off is one extra click per replay session.

### 5. Move SERVER and other constants to settings (trivial)

Same as it was in 2.5.0's "next steps" — currently not done because it wasn't needed.

### 6. Wider `strip_format_tags()` coverage (low effort, reactive)

If/when a WOD or FOD feed surfaces a malformed BBCode tag the current regex doesn't catch, widen the regex and add a unit test. The function lives in `wrestling.py` next to the other text helpers.

### 7. Genre icon refresh (low effort, cosmetic, unchanged from 2.5.0)

The `resources/images/genres/` directory has bundled icons for all the IPTV genre categories plus several wrestling/UFC/boxing labels used by the new STATIC_MENUS. If any icon needs updating, drop a new `256x256 RGBA PNG` file in there — transparent background, white graphic — and it'll be picked up automatically. The `_menu_icon()` helper in default.py looks up icons by exact filename match.

---

## Code Health

The codebase is in good shape as of v2.6.0. There is no dead code, no disabled features, no commented-out blocks. Every function does one thing. The separation between the data layer (`wrestling.py`) and the Kodi UI layer (`default.py`) is clean and has held up through multiple rounds of changes.

The v2.6.0 integration was scope-controlled: no new dependencies, no new third-party modules, no new resolver paths. The wrestling.py changes are additive (one tag alias and one new utility function) — they cannot regress existing Wrestling Rewind behaviour. The default.py changes consist of one new view function (`list_static_menu`), one new helper (`_menu_icon`), one data structure (`STATIC_MENUS`), two new root entries, one new router branch, plus the audit-pass improvements to `list_wr` and `cache_clear_all`.

The main ongoing risk is the upstream feeds. They are third-party external services with no SLA. If `mylostsoulspace.co.uk` or `l3grthu.com` go offline or change their XML structure significantly, the affected sections will stop working. The fallback path (pass 4 per-item extraction) buys a lot of resilience against structural changes, but a completely different feed format would require parser updates.

Feed URLs are soft-coded:
- Wrestling Rewind: one constant in `default.py`, readable from settings if `wr_root_url` is set
- Wrestling on Demand: `WOD_BASE` constant + `STATIC_MENUS['wod_*']` paths
- Fights on Demand: `FOD_BASE` constant + `STATIC_MENUS['fod_*']` paths

Pointing at a mirror is an edit to a handful of lines.

---

## File Checksums (v2.6.0)

For verifying a clean install:

```
default.py        ~1580 lines, ~63KB
wrestling.py      ~680 lines, ~26KB
settings.xml      4 settings (unchanged from 2.5.0)
addon.xml         resolveurl as hard import (unchanged from 2.5.0)
README.md         this file's companion
HANDOFF.md        this file
```
