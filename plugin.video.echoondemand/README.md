# Echo OnDemand — Kodi Video Plugin

**Version:** 2.6.0
**Platform:** Kodi Omega (v21) — Windows, Linux, macOS, Android
**Developer:** Echo-Storm

---

## What It Does

Echo OnDemand is a private Kodi addon that provides access to five content sources from a single root menu:

- **Movies** — browse by genre, search by title or year, play via Xtream Codes IPTV
- **Series** — full season and episode navigation via Xtream Codes IPTV
- **Wrestling** — Wrestling Rewind replays and PPV events via debrid
- **Wrestling on Demand** — WWE (RAW, SmackDown, NXT, WrestleMania, PPV), AEW, TNA, NWA, NJPW, ROH, RPW, Indy, plus documentaries, interviews, special matches, archive
- **Fights on Demand** — UFC (PPV, Fight Night, ESPN/ABC/FOX/FUEL, Classic, Shows), MMA, Boxing, including a Free / No Debrid sub-menu

Designed for a small, known user group (~4 installs). Not publicly distributed.

---

## Requirements

| Component | Required | Notes |
|---|---|---|
| Kodi 21 (Omega) | Yes | Python 3 required |
| Xtream Codes IPTV service | For Movies/Series | Not needed for Wrestling/Fights |
| `script.module.resolveurl` | Yes | Hard dependency — install via repo |
| Active debrid account (Real-Debrid etc.) | Recommended | Configure in resolveurl settings; FOD has a Free / No Debrid sub-menu for users without one |
| TMDB API key | No | Optional — enables movie backdrop art |

The three replay sections (Wrestling, Wrestling on Demand, Fights on Demand) are accessible without IPTV credentials. Movies and Series will prompt for credentials if not set.

---

## Installation

Install as a zip file via Kodi's Add-on Manager:

1. Settings → Add-ons → Install from zip file
2. Select `plugin_video_echoondemand-2_6_0.zip`
3. Open the addon and enter your Xtream Codes username and password in Settings

Ensure `script.module.resolveurl` is already installed before enabling the addon.

---

## Settings

| Setting | Purpose |
|---|---|
| Username | Xtream Codes username |
| Password | Xtream Codes password |
| Pre-buffer seconds | Seconds to pause before playback begins (0 = disabled). Gives Kodi's buffer time to fill before the first frame. |
| TMDB API key | Optional. When present, fetches and caches movie backdrops after each play. Free key from themoviedb.org. |

No source-specific settings are exposed. Feed root URLs are hardcoded in `default.py` (one constant per source). The Wrestling Rewind root URL can be overridden via a `wr_root_url` setting if added to settings.xml manually; WOD and FOD roots are static category trees defined in `STATIC_MENUS` near the top of `default.py`.

---

## Content Sources

### Movies and Series (Xtream Codes IPTV)

Stream URLs are built at play time from the configured server:
```
Movie:   https://<server>/movie/<user>/<pass>/<vod_id>.<ext>
Episode: https://<server>/series/<user>/<pass>/<episode_id>.<ext>
```

The server address is hardcoded in `default.py` (`SERVER` constant). To point the addon at a different server, change that one line. There is no settings UI for the server URL by design — the user base is small and stable.

### Wrestling (Wrestling Rewind via debrid)

Content comes from a remote MicroJen XML/JSON feed at `mylostsoulspace.co.uk/WrestlingRewind/`. The feed describes a directory tree of wrestling shows and events. Each leaf item contains one or more candidate links (magnet URIs and/or direct HTTP hosters).

### Wrestling on Demand (WOD via debrid)

Content comes from MicroJen XML feeds at `l3grthu.com/hades/wod21/`. The upstream service does not provide a single master menu XML, so the menu structure is curated in `STATIC_MENUS['wod_root']` and its sub-menus (`wod_wwe`, `wod_other`). Each leaf is a directory item that hands off to the standard MicroJen feed walker.

Live channels from this source are deliberately excluded — Echo OnDemand is for replays only.

### Fights on Demand (FOD via debrid)

Content comes from MicroJen XML feeds at `mylostsoulspace.co.uk/FightsOnDemand/`. Same hosting domain as Wrestling Rewind. The menu is curated in `STATIC_MENUS['fod_root']` (Latest, UFC Events, MMA, Boxing, Free) with a UFC sub-menu (`fod_ufc`) and Free / No Debrid sub-menu (`fod_free`).

The Free sub-menu points at the upstream's nondebrid feeds for users without a debrid account.

### Link resolution (all replay sources)

At play time, `resolve_best_link()` in `wrestling.py` tries each link in order:
1. **Debrid** — `resolveurl.HostedMediaFile(link).resolve()`. First successful result wins.
2. **Direct video** — any link with a recognisable video extension (`.mp4`, `.mkv`, `.m3u8`, etc.)
3. **HTTP fallback** — first HTTP URL, played directly by Kodi

The user sees none of this — it either plays or shows an error notification. The same code path serves all three replay sources because they share the MicroJen feed format.

---

## File Structure

```
plugin.video.echoondemand/
  addon.xml                  Kodi metadata, dependencies (includes resolveurl)
  default.py                 Entire plugin — routing, views, IPTV data layer,
                             STATIC_MENUS for WOD/FOD curated trees
  icon.png                   Addon icon (256x256)
  fanart.jpg                 Addon background fanart
  resources/
    settings.xml             Four user-facing settings
    __init__.py
    lib/
      __init__.py
      wrestling.py           MicroJen feed data layer — fetch, parse, resolve.
                             Source-agnostic: handles WR, WOD, and FOD feeds
                             with the same code paths.
    images/
      genres/                PNG icons for IPTV genre categories (256x256 RGBA)
        Action.png
        Comedy.png
        Wrestling.png        Used by WOD/FOD menus where bundled icons match
        WWE RAW.png
        WWE SmackDown.png
        NXT.png
        AEW.png
        UFC Replays.png
        Boxing Replays.png
        ... (40+ files)
```

---

## Architecture

### default.py

A single-file plugin following Kodi's standard pattern:

- `router(paramstring)` — reads URL params, dispatches to the right view function
- One `list_*` function per directory view, one `play_*` function per playable type
- `STATIC_MENUS` dict at module top defines the WOD and FOD curated trees as pure data
- `list_static_menu(menu_key, title)` renders one level of a static tree; entries either drill into another static menu or hand off to `list_wr` against a feed XML
- Cache uses `{ts, payload}` JSON files in the addon profile directory
- TMDB fanart is a separate persistent JSON cache, populated lazily at play time, preserved across "Refresh / Clear Cache"

**Content type decisions (important for skin behaviour):**

| View | `setContent()` | Reason |
|---|---|---|
| Root | `addons` | Prevents skin's episode info panel from rendering |
| Movie categories | `files` | Suppresses skin's right-panel info slot for genre lists |
| Movies | `movies` | Full movie metadata panel |
| Series categories | `files` | Same as movie categories |
| Series | `tvshows` | Full TV show metadata |
| Seasons | `seasons` | Kodi season view |
| Episodes | `episodes` | Episode list with info panel |
| Wrestling / WOD / FOD (any level) | `files` | Right panel suppressed; Plot still set on items so the Info button works |

### resources/lib/wrestling.py

Pure data layer — no Kodi UI calls. Importable and testable in isolation. Originally built for Wrestling Rewind; now also drives Wrestling on Demand and Fights on Demand because all three sources use the same MicroJen format.

Three logical sections:
1. **Cache** — `cache_load()` / `cache_save()` — raw feed text keyed by sanitised URL
2. **Parse** — `parse_feed()` dispatches to `parse_xml()` or `parse_json()`. XML parser has four recovery passes including a per-item regex fallback for broken feeds. Aliases the WOD-specific `<summaru>` typo to `summary`.
3. **Resolve** — `resolve_best_link()` — debrid first, direct video second, HTTP fallback third

Plus `strip_format_tags()` — text utility for cleaning Kodi BBCode-style noise (`[COLOR ...]`, `[B]`, `[I]`, malformed variants) out of titles for display. Kept in this module because it sits next to the other text-cleaning helpers and the UI calls it.

### Cache system

All cache files live in `xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))`.

| File pattern | TTL | Contents |
|---|---|---|
| `movie_cats.json` | 1 hour | Movie genre list from API |
| `series_cats.json` | 1 hour | Series genre list from API |
| `movies_{cat_id}.json` | 30 min | Stream list for one movie category |
| `series_{cat_id}.json` | 30 min | Stream list for one series category |
| `seriesinfo_{id}.json` | 1 hour | Full season/episode data for one series |
| `tmdb_fanart.json` | Permanent | TMDB backdrop URL cache (preserved across "Refresh / Clear Cache") |
| `wr_{url_hash}.json` | 30 min | MicroJen feed cache — covers WR, WOD, and FOD |

"Refresh / Clear Cache" in the root menu deletes all `*.json` files from the profile directory **except `tmdb_fanart.json`**, which is preserved because it represents many plays of accumulated work and is independent of the IPTV / wrestling / fights content the user actually wants to refresh.

---

## Adding a New Content Section

There are two patterns depending on whether the upstream source has a single master menu XML.

### Pattern A: source has a master menu XML (like Wrestling Rewind)

1. **Add a root entry** in `list_root()` that points `mode=wr_list` at the master XML URL.
2. Done. Existing `list_wr` walks the tree from there.

### Pattern B: source needs a curated tree (like WOD or FOD)

1. **Add entries to `STATIC_MENUS`** at the top of `default.py`. Use existing WOD/FOD entries as templates.
2. **Add a root entry** in `list_root()` that points `mode=static_menu&key=<your_key>` at the new menu.
3. Done. `list_static_menu` and `list_wr` cover the rest.

### Pattern C: completely different feed format

If the source uses neither MicroJen XML nor JSON:

1. Create `resources/lib/{source}.py` mirroring the structure of `wrestling.py` (fetch, parse, resolve). No Kodi UI calls.
2. Add `list_{source}` and `play_{source}` functions in `default.py` following `list_wr` / `play_wr` exactly.
3. Wire up the router with new modes.
4. Add a root entry in `list_root()`.

No changes to `addon.xml` unless the new source requires an additional Kodi module dependency.

---

## Skin Notes (Aeon Nox Silvo)

The addon was developed and tested against Aeon Nox Silvo. Two skin files were modified alongside the addon to suppress unwanted info panels:

- `MyVideoNav.xml` — ghost control reference removed; info panel conditions added
- `View_50_List.xml` — right-side info panel suppressed when `Container.Content(files)` and `Container.PluginName` match

If the skin is updated or replaced, the `setContent()` values above may need revisiting. The most visible symptom of a mismatch is an empty info panel on the right side of a genre category list, or for the Wrestling/WOD/FOD lists.

The v2.6.0 change of setting `Plot` via `InfoTagVideo` on Wrestling/WOD/FOD items does NOT bring the right panel back — the suppression depends on `Container.Content(files)`, not on whether items have InfoTag data.

---

## Troubleshooting

**"No items found in this section" on a Wrestling / WOD / FOD sub-feed**
Clear the cache (root menu → Refresh / Clear Cache) and retry. If it persists, check the Kodi log for `[EchoOD/Wrestling] PARSE FAILED` — the log line includes the first 300 characters of the raw feed for diagnosis.

**Wrestling / WOD / FOD item plays blank / "Could not resolve stream"**
Check the Kodi log for `[EchoOD/Wrestling] resolve_best_link` lines. These are logged at INFO level (no debug mode needed). They show each candidate URL, whether resolveurl accepted it, and which pass was used. Most likely cause: debrid account not configured in resolveurl settings, or the hoster is not supported. For FOD, the Free / No Debrid sub-menu is available as a workaround.

**WOD/FOD titles show literal `[COLOR ...]` or `[B]` text**
This means a malformed BBCode tag passed through `strip_format_tags()`. Open an issue with the exact title string so the regex can be widened.

**Movies/Series show "Please enter credentials" on every open**
Enter username and password in Settings (addon settings, not Kodi system settings). The server address is hardcoded — only credentials are user-configurable.

**Kodi hangs loading a category (spinning indefinitely)**
Fixed in v2.5.0. All error paths now call `endOfDirectory(succeeded=False)`. If this occurs on v2.5.0+, it is a new error path that was missed — check the Kodi log for `[EchoOD]` entries around the time of the hang.

**Cache cleared but TMDB backdrops are still cached**
Intentional in v2.6.0. The TMDB cache (`tmdb_fanart.json`) is preserved across "Refresh / Clear Cache" because it accumulates over many plays. To wipe it, delete the file manually from the addon profile directory.
