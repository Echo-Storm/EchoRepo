# Echo OnDemand — Kodi Video Plugin

**Version:** 3.1.0
**Platform:** Kodi Omega (v21) — Windows, Linux, macOS, Android
**Developer:** Echo-Storm

---

## What It Does

Echo OnDemand is a private Kodi addon that provides access to six content sources from a single root menu:

- **Movies** — browse by genre, search by title or year, play via Xtream Codes IPTV
- **Series** — full season and episode navigation via Xtream Codes IPTV
- **Wrestling Rewind** — Wrestling Rewind replays and PPV events via debrid
- **Wrestling on Demand** — WWE (RAW, SmackDown, NXT, WrestleMania, PPV), AEW, TNA, NWA, NJPW, ROH, RPW, Indy, plus documentaries, interviews, special matches, archive
- **Fights on Demand** — UFC (PPV, Fight Night, ESPN/ABC/FOX/FUEL, Classic, Shows), MMA, Boxing, including a Free / No Debrid sub-menu
- **Live** — Live Wrestling (24/7 channels from WOD's `live.xml`) and Sports Streams (curated Pluto TV themed sports channels: Golf Central, F1, UFC, Bellator, ONE, Top Rank Classics, DAZN Ringside)

Plus three menu actions: **Backup Settings**, **Restore Settings**, and **Refresh / Clear Cache**.

Designed for a small, known user group (~4 installs). Not publicly distributed.

---

## Requirements

| Component | Required | Notes |
|---|---|---|
| Kodi 21 (Omega) | Yes | Python 3 required |
| Xtream Codes IPTV service | For Movies/Series | Not needed for replay/live sections |
| `script.module.resolveurl` | Yes | Hard dependency — install via repo |
| Active debrid account (Real-Debrid etc.) | Recommended | Configure in resolveurl settings; FOD has a Free / No Debrid sub-menu for users without one |
| TMDB API key | No | Optional — enables movie backdrop art |

The replay and live sections are accessible without IPTV credentials. Movies and Series will prompt for credentials if not set.

---

## Installation

Install as a zip file via Kodi's Add-on Manager:

1. Settings → Add-ons → Install from zip file
2. Select `plugin_video_echoondemand-3_1_0.zip`
3. Open the addon and enter your Xtream Codes username and password in Settings

Ensure `script.module.resolveurl` is already installed before enabling the addon.

### Upgrading from a previous version

**Important:** if you want your settings (username/password/etc.) to persist, install the new zip OVER the existing addon. Don't uninstall first.

- ✅ **Install from zip → pick new zip** → Kodi treats this as an update. Your `userdata/addon_data/plugin.video.echoondemand/settings.xml` is left alone.
- ❌ **Uninstall the addon first → then Install from zip** → Kodi wipes the addon's userdata folder. Settings are lost.

If you've ever lost settings between versions, that's why. v3.0.0 adds a **Backup Settings / Restore Settings** pair as a safety net (see below) — so even if you do uninstall+reinstall, you can get your credentials back in one click.

---

## Settings

| Setting | Purpose |
|---|---|
| Username | Xtream Codes username |
| Password | Xtream Codes password |
| Pre-buffer seconds | Seconds to pause before playback begins (0 = disabled). Gives Kodi's buffer time to fill before the first frame. |
| TMDB API key | Optional. When present, fetches and caches movie backdrops after each play. Free key from themoviedb.org. |
| Use Pluto TV resolver | Default on. Resolves Pluto channels with a fresh session at play time. Turn off only if Pluto changes their boot API and the resolver starts failing — the addon will fall back to the original (potentially stale) URLs from the upstream feed. |

No source-specific settings are exposed. Feed root URLs are hardcoded in `default.py` (one constant per source). The Wrestling Rewind root URL can be overridden via a `wr_root_url` setting if added to settings.xml manually; WOD, FOD, and Live roots are static category trees defined in `STATIC_MENUS` near the top of `default.py`.

### Backup / Restore Settings (new in 3.0.0)

Two root menu entries write and read a JSON snapshot of all four user settings to `special://userdata/echoondemand_settings.json`. This file lives **one level up** from the addon's own userdata directory and is not affected when Kodi cleans up the addon's userdata on uninstall.

- **Backup Settings** — writes the snapshot (no confirmation, takes a moment, shows a notification on success).
- **Restore Settings** — reads the snapshot, confirms with a yes/no dialog, then writes each value back via `ADDON.setSetting()`. The file's `version` field is checked; backups from a future addon version are refused rather than silently corrupting the schema.

Take a backup any time you've configured the addon to your liking. The file is small (a few hundred bytes) and human-readable.

---

## Content Sources

### Movies and Series (Xtream Codes IPTV)

Stream URLs are built at play time from the configured server:
```
Movie:   https://<server>/movie/<user>/<pass>/<vod_id>.<ext>
Episode: https://<server>/series/<user>/<pass>/<episode_id>.<ext>
```

The server address is hardcoded in `default.py` (`SERVER` constant). To point the addon at a different server, change that one line.

### Wrestling Rewind (via debrid)

Content comes from a remote MicroJen XML/JSON feed at `mylostsoulspace.co.uk/WrestlingRewind/`. The feed describes a directory tree of wrestling shows and events. Each leaf item contains one or more candidate links (magnet URIs and/or direct HTTP hosters).

### Wrestling on Demand (WOD via debrid)

Content comes from MicroJen XML feeds at `l3grthu.com/hades/wod21/`. The upstream service does not provide a single master menu XML, so the menu structure is curated in `STATIC_MENUS['wod_root']` and its sub-menus (`wod_wwe`, `wod_other`). Each leaf is a directory item that hands off to the standard MicroJen feed walker.

### Fights on Demand (FOD via debrid)

Content comes from MicroJen XML feeds at `mylostsoulspace.co.uk/FightsOnDemand/`. Same hosting domain as Wrestling Rewind. The menu is curated in `STATIC_MENUS['fod_root']` (Latest, UFC Events, MMA, Boxing, Free) with a UFC sub-menu (`fod_ufc`) and Free / No Debrid sub-menu (`fod_free`).

The Free sub-menu points at the upstream's nondebrid feeds for users without a debrid account.

### Live (expanded in 3.1.0)

Two sub-categories:

- **Live Wrestling** — walks WOD's `live.xml` feed (24/7 wrestling channels). Channels are dynamic; the upstream service adds and removes them.
- **Sports Streams** — curated list of Pluto TV themed sports channels (Golf Central, F1, UFC, Bellator MMA, ONE Championship, Top Rank Classics, DAZN Ringside). The list lives in `STATIC_MENUS['live_sports']` in `default.py` — adding a channel is a one-line edit (find the channel ID in the URL bar of `pluto.tv/us/live-tv/<id>` and add an entry).

Both sub-categories resolve through `resources/lib/pluto.py`, which fetches a fresh session from `boot.pluto.tv` at play time. This sidesteps the stale-session-token issue that previously caused some channels in WOD's `live.xml` to play "service no longer available" videos instead of the actual channel — those videos came from regional Pluto retirement notices triggered by tokens that had been minted in regions Pluto has since pulled out of. By minting our own session from the user's actual region, we get the live channel every time the channel is available in that region.

If a Pluto channel still fails to play in 3.1.0+, it's almost always because the channel itself isn't available in your region — Pluto geo-locks some content. Same channel ID may work for one user and not another.

### Link resolution (all replay and live sources)

At play time, `resolve_best_link()` in `wrestling.py` tries each link in order:
1. **Debrid** — `resolveurl.HostedMediaFile(link).resolve()`. First successful result wins.
2. **Direct video** — any link with a recognisable video extension (`.mp4`, `.mkv`, `.m3u8`, etc.)
3. **HTTP fallback** — first HTTP URL, played directly by Kodi

The user sees none of this — it either plays or shows an error notification. The same code path serves all four MicroJen-format sources (WR, WOD, FOD, Live) because they share the feed format.

---

## File Structure

```
plugin.video.echoondemand/
  addon.xml                  Kodi metadata, dependencies (includes resolveurl)
  default.py                 Entire plugin — routing, views, IPTV data layer,
                             STATIC_MENUS for WOD/FOD/Live curated trees,
                             settings backup/restore
  icon.png                   Addon icon (256x256)
  fanart.jpg                 Addon background fanart
  resources/
    settings.xml             Four user-facing settings
    __init__.py
    lib/
      __init__.py
      wrestling.py           MicroJen feed data layer — fetch, parse, resolve.
                             Source-agnostic: handles WR, WOD, FOD, Live with
                             the same code paths.
    images/
      genres/                PNG icons (256x256 RGBA, template-style)
        Action.png, Comedy.png, Wrestling.png  (refreshed in 3.0.0)
        WWE RAW.png, WWE SmackDown.png, NXT.png, AEW.png, AEW Collision.png
        TNA.png, NWA.png, NJPW.png, ROH.png, RPW.png, Indy Wrestling.png  (new in 3.0.0)
        UFC Replays.png, Boxing Replays.png, MMA.png  (MMA new in 3.0.0)
        Live.png, Live Wrestling.png  (new in 3.0.0)
        WrestleMania.png, PPV Events.png, Latest Shows.png, Free.png
        Wrestling on Demand.png, Fights on Demand.png  (new in 3.0.0)
        ... (50+ files total)
```

---

## Architecture

### default.py

A single-file plugin following Kodi's standard pattern:

- `router(paramstring)` — reads URL params, dispatches to the right view function
- One `list_*` function per directory view, one `play_*` function per playable type
- `STATIC_MENUS` dict at module top defines the WOD, FOD, and Live curated trees as pure data
- `list_static_menu(menu_key, title)` renders one level of a static tree; entries either drill into another static menu or hand off to `list_wr` against a feed XML
- `do_settings_backup()` / `do_settings_restore()` write/read a JSON snapshot to `special://userdata/`
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
| WR / WOD / FOD / Live (any level) | `files` | Right panel suppressed; Plot still set on items so the Info button works |

### resources/lib/wrestling.py

Pure data layer — no Kodi UI calls. Importable and testable in isolation. Originally built for Wrestling Rewind; now drives WOD, FOD, and Live too because all four sources use the same MicroJen format.

Three logical sections:
1. **Cache** — `cache_load()` / `cache_save()` — raw feed text keyed by sanitised URL
2. **Parse** — `parse_feed()` dispatches to `parse_xml()` or `parse_json()`. XML parser has four recovery passes including a per-item regex fallback for broken feeds. Aliases the WOD-specific `<summaru>` typo to `summary`.
3. **Resolve** — `resolve_best_link()` — debrid first, direct video second, HTTP fallback third

Plus `strip_format_tags()` — text utility for cleaning Kodi BBCode-style noise (`[COLOR ...]`, `[B]`, `[I]`, malformed variants) out of titles for display.

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
| `wr_{url_hash}.json` | 30 min | MicroJen feed cache — covers WR, WOD, FOD, Live |

"Refresh / Clear Cache" deletes all `*.json` files from the profile directory **except `tmdb_fanart.json`**, which is preserved because it represents many plays of accumulated work.

### Settings persistence

Kodi's per-addon userdata layout (which Echo OnDemand uses unmodified):

```
<KODI_HOME>/userdata/
  addon_data/
    plugin.video.echoondemand/
      settings.xml          ← username, password, etc. (Kodi-managed)
      *.json                ← cache files (addon-managed)
  echoondemand_settings.json  ← Backup/Restore snapshot (addon-managed, new in 3.0.0)
```

`addon_data/plugin.video.echoondemand/` is wiped on uninstall. `echoondemand_settings.json` (one level up) survives uninstall and is the safety net the Backup/Restore feature relies on.

---

## Adding a New Content Section

There are three patterns depending on what the upstream source looks like.

### Pattern A: source has a master menu XML (like Wrestling Rewind)

1. **Add a root entry** in `list_root()` that points `mode=wr_list` at the master XML URL.
2. Done. Existing `list_wr` walks the tree from there.

### Pattern B: source needs a curated tree (like WOD, FOD, Live)

1. **Add entries to `STATIC_MENUS`** at the top of `default.py`. Use existing entries as templates.
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

If the skin is updated or replaced, the `setContent()` values above may need revisiting. The most visible symptom of a mismatch is an empty info panel on the right side of a category list.

---

## Troubleshooting

**"No items found in this section" on a Wrestling / WOD / FOD / Live sub-feed**
Clear the cache (root menu → Refresh / Clear Cache) and retry. If it persists, check the Kodi log for `[EchoOD/Wrestling] PARSE FAILED` — the log line includes the first 300 characters of the raw feed for diagnosis.

**Item plays blank / "Could not resolve stream"**
Check the Kodi log for `[EchoOD/Wrestling] resolve_best_link` lines. These are logged at INFO level (no debug mode needed). They show each candidate URL, whether resolveurl accepted it, and which pass was used. Most likely cause: debrid account not configured in resolveurl settings, or the hoster is not supported. For FOD, the Free / No Debrid sub-menu is available as a workaround.

**Titles show literal `[COLOR ...]` or `[B]` text**
This means a malformed BBCode tag passed through `strip_format_tags()`. Open an issue with the exact title string so the regex can be widened.

**Movies/Series show "Please enter credentials" on every open**
Enter username and password in Settings (addon settings, not Kodi system settings). The server address is hardcoded — only credentials are user-configurable.

**Kodi hangs loading a category (spinning indefinitely)**
Fixed in v2.5.0. All error paths now call `endOfDirectory(succeeded=False)`. If this occurs on v2.5.0+, it is a new error path that was missed — check the Kodi log for `[EchoOD]` entries around the time of the hang.

**Cache cleared but TMDB backdrops are still cached**
Intentional in v2.6.0+. The TMDB cache (`tmdb_fanart.json`) is preserved across "Refresh / Clear Cache" because it accumulates over many plays. To wipe it, delete the file manually from the addon profile directory.

**A live channel fails to play with "Error creating demuxer" in the Kodi log**
Some live channels are HLS streams served by Pluto TV's stitcher (or other HLS sources) — Kodi's built-in demuxer can fail on these. v3.0.1+ hands HLS URLs to `inputstream.adaptive` automatically, which handles them more reliably. If it still fails: confirm `inputstream.adaptive` is installed and enabled (Add-ons → My add-ons → VideoPlayer InputStream → InputStream Adaptive).

**A Pluto TV channel plays a "service no longer available" video instead of the live channel**
This was the dominant failure mode in v3.0.x — stale session tokens baked into WOD's upstream `live.xml` feed pointed at regional Pluto retirement notices. v3.1.0 fixes this by minting fresh session tokens at play time via Pluto's boot endpoint. If you still see a retirement notice on v3.1.0+, the channel itself has been pulled in your region — Pluto geo-locks some content per-channel.

**A Pluto TV live channel fails with "HTTP error 403" from inputstream.adaptive**
v3.0.2+ injects a Chrome-shaped User-Agent and a `pluto.tv` Referer for any URL containing `pluto.tv` to clear this. If a Pluto channel still 403s on v3.1.0+, run "Refresh / Clear Cache" — the in-memory Pluto session may have aged out unusually. If that doesn't help, check the Kodi log for `pluto:` lines around the time of the failure.

**The Pluto resolver itself is misbehaving**
You can disable it in Settings → "Use Pluto TV resolver". When off, the addon falls back to playing whatever stitcher URL was in the upstream feed (the v3.0.2 behaviour). Use this as a temporary workaround only — you'll lose access to the curated Sports Streams channels entirely, and live wrestling becomes hit-or-miss again. Re-enable as soon as the underlying issue is resolved.

**Lost settings after reinstalling the addon**
Use the Backup Settings entry before uninstalling, and Restore Settings after reinstalling. See "Upgrading from a previous version" above for prevention. Backup file lives at `<KODI_HOME>/userdata/echoondemand_settings.json`.

**"Backup is from a newer addon version" on restore**
You're trying to restore a backup made by a later Echo OnDemand into an earlier one. This is refused on purpose — the backup schema may have changed. Either upgrade the addon to a version >= the one in the backup file's `version` field, or ignore the backup and re-enter settings manually.
