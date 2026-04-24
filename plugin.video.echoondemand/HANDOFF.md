# Echo OnDemand — Developer Handoff Notes

**Handed off at:** v2.5.0  
**Status:** Stable and working  

This document is for whoever picks this up next — including future-me. It covers what the code is doing, why specific decisions were made, what was deliberately left out, and what the natural next steps are.

---

## Current State

The addon works reliably across all three content sections on Kodi 21 Omega (Windows). Tested in production with Real-Debrid. The main areas of development since v2.0 were the Wrestling integration, which went through several rounds of XML parser debugging against live feeds. All known bugs are fixed as of v2.5.0.

**What works:**
- Movies and Series via Xtream Codes, including genre icons, TMDB backdrop caching, pre-buffer, context menus
- Wrestling navigation — full directory tree, sub-feeds, PPV feeds (which had structural XML issues now handled by a 4-pass parser)
- Debrid resolution — magnet URIs and HTTP hosters, with proper label stripping and ResolvedURL object handling
- Cache system — all content types, including Wrestling feeds in the profile directory
- Clean navigation history — Refresh/Clear Cache does not pollute the back stack

**What was deliberately excluded:**
- Trakt integration (removed from Wrestling Rewind source, never added to IPTV side)
- Server URL in settings — hardcoded by design for this user base
- Wrestling-specific settings — TTL is fixed at 30 min, root URL is hardcoded with a one-line change point

---

## Key Design Decisions

### Why `setContent('files')` for category and Wrestling views

This is the single most important thing to understand about the skin behaviour. Aeon Nox Silvo renders a large info panel on the right side for `movies`, `tvshows`, and `videos` content. For category lists (genre folders) and Wrestling (no metadata), this panel either shows nothing or shows the genre icon scaled up in an ugly way.

`setContent('files')` tells the skin "this is a generic file browser, not a media library view" — the right panel is suppressed. The companion skin XML changes (MyVideoNav.xml, View_50_List.xml) reinforce this with explicit `Container.Content(files)` conditions.

If the skin is ever replaced or updated, audit the `setContent()` value for each view and check what the skin does with it.

### Why `script.module.resolveurl` is a hard dependency

Everyone who uses this addon has Real-Debrid configured. Making resolveurl optional would require adding a toggle in settings and building a path that tries direct play for everything — that path exists as a fallback in `resolve_best_link()` anyway, but the UX assumption throughout is that debrid works. If that ever changes, the hard dependency in `addon.xml` can be softened and the `_RESOLVEURL_OK` flag in `wrestling.py` already handles the no-resolveurl case gracefully.

### Why Wrestling lives in a separate `wrestling.py`

The MicroJen XML format has quirks (multiple valid nesting structures, broken documents, preamble obfuscation, label-suffixed links, two URI schemes) that would have cluttered `default.py` badly. More importantly, it's a data layer that can be reasoned about in isolation. If the Wrestling source changes or a new source with similar structure is added, `wrestling.py` is the right place to extend — not `default.py`.

### Why `base64 JSON` encoding for Wrestling play items

Wrestling items can have a list of sublinks (multiple candidate URLs). Passing a list through a URL parameter cleanly requires some form of serialisation. Base64-encoded JSON is the approach Wrestling Rewind's own code uses internally — it's compact, round-trips without encoding issues, and keeps `play_wr()` self-contained. The alternative would be per-field URL params, which breaks for list-typed fields.

### Why the pre-buffer works the way it does

`xbmc.Player.isPaused()` does not exist in Kodi Omega. The correct check is `xbmc.getCondVisibility('Player.Paused')`. This is documented in `_apply_buffer()` with an explicit comment because it's a common wrong assumption. The approach — poll for playing, pause, sleep, resume if still paused — is the same technique used by several established addons. It runs after `setResolvedUrl` because the plugin process stays alive until the Python interpreter exits, which happens well after playback starts.

---

## The Wrestling XML Parser — What Was Actually Happening

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
WR appends human-readable labels to link URLs in parentheses: `https://host.com/file.mkv(Non Debrid)`. These must be stripped. The original stripping code only accepted `http` prefixes — magnet links (which start `magnet:`) had their labels NOT stripped, so resolveurl received broken magnet URIs. Fixed in v2.3.

---

## Known Limitations

**The server URL is hardcoded.** `SERVER = 'https://blueonesuperoceanhere.com'` in `default.py`. This is a deliberate choice for this deployment, not an oversight. If the server changes, it's a one-line edit. If a settings UI is needed, add `<setting id="server_url" .../>` to settings.xml, read it in `get_credentials()`, and update `play_movie()` and `play_episode()` to use the setting.

**TMDB cache never expires.** The `tmdb_fanart.json` file grows unboundedly over time as more movies are played. In practice this is not a problem for a small library, but for a large one it would eventually slow down `_load_tmdb_cache()` (which loads the full file on every movie list load). If the library grows significantly, add TTL-per-entry or periodic pruning.

**`cache_clear_all()` is nuclear.** It deletes every `*.json` in the profile directory, including the TMDB fanart cache. This means clearing cache after a Wrestling issue also clears all the TMDB backdrops that took many plays to accumulate. Consider separating them: keep `tmdb_fanart.json` exempt from `cache_clear_all()`, or add a separate "Clear TMDB cache" option.

**Wrestling feed cache uses URL-based filenames.** `_cache_filename()` sanitises the URL to produce a filename. If two URLs somehow sanitise to the same string (very unlikely in practice), there would be a collision. Not worth fixing unless it actually happens.

**No retry logic on network failure.** If the IPTV API or the WR feed returns a network error, the user sees a dialog and the directory fails. There is no automatic retry. For a hobbyist addon this is fine — manual retry (re-open the folder) is the expected behaviour.

---

## Natural Next Steps

These are the things that logically come next, in rough order of effort:

### 1. Add a second wrestling source (low effort)

The architecture is ready for it. `wrestling.py` is source-agnostic — it handles MicroJen XML/JSON regardless of where the feed comes from. Add a second Wrestling sub-section in `list_wr` or add a parallel source entry in `list_root`. The only work is finding a compatible feed and testing the parser against it.

### 2. Add sports replays section (medium effort)

The old `plugin.video.echosports` architecture had LeagueDo, pitsport.xyz, and Wrestling on Demand as sources. LeagueDo and pitsport.xyz were working. These could be ported as `resources/lib/sports.py` following the same pattern as `wrestling.py`. The routing and UI changes would be ~30 lines in `default.py`.

### 3. Move SERVER to settings (trivial)

Add one setting, read it in `get_credentials()`, propagate to `play_movie()` and `play_episode()`. ~10 lines total. Currently not done because it wasn't needed.

### 4. Protect TMDB cache from clear-all (trivial)

Either move `tmdb_fanart.json` to a different directory, or modify `cache_clear_all()` to exclude it by name. ~2 lines.

### 5. Genre icon refresh (low effort, cosmetic)

The `resources/images/genres/` directory has bundled icons for all the IPTV genre categories. Some of these are placeholder-quality. If the icons need updating, drop new `256x256 RGBA PNG` files in there — transparent background, white graphic — and they'll be picked up automatically by `get_genre_icon()` on the next install. Existing `Wrestling.png` is available if the root entry ever needs a distinct icon.

---

## Code Health

The codebase is in good shape as of v2.5.0. There is no dead code, no disabled features, no commented-out blocks. Every function does one thing. The separation between the data layer (`wrestling.py`) and the Kodi UI layer (`default.py`) is clean and has held up through multiple rounds of changes.

The main ongoing risk is the WR feed. It is a third-party external service with no SLA. If `mylostsoulspace.co.uk` goes offline or changes its XML structure significantly, the Wrestling section will stop working. The fallback path (pass 4 per-item extraction) buys a lot of resilience against structural changes, but a completely different feed format would require parser updates. The feed URL is soft-coded (one constant in `default.py`, readable from settings if `wr_root_url` is set) so a mirror URL can be pointed at without a code change.

---

## File Checksums (v2.5.0)

For verifying a clean install:

```
default.py        ~1300 lines, ~50KB
wrestling.py      ~632 lines, ~24KB  
settings.xml      4 settings
addon.xml         resolveurl as hard import
README.md         this file's companion
HANDOFF.md        this file
```
