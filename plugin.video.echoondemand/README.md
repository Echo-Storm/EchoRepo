# Echo OnDemand — Kodi Video Plugin

**Version:** 2.5.0  
**Platform:** Kodi Omega (v21) — Windows, Linux, macOS, Android  
**Developer:** Echo-Storm  

---

## What It Does

Echo OnDemand is a private Kodi addon that provides access to three content sources from a single root menu:

- **Movies** — browse by genre, search by title or year, play via Xtream Codes IPTV
- **Series** — full season and episode navigation via Xtream Codes IPTV
- **Wrestling** — Wrestling Rewind replays and PPV events via debrid

Designed for a small, known user group (~4 installs). Not publicly distributed.

---

## Requirements

| Component | Required | Notes |
|---|---|---|
| Kodi 21 (Omega) | Yes | Python 3 required |
| Xtream Codes IPTV service | For Movies/Series | Not needed for Wrestling |
| `script.module.resolveurl` | Yes | Hard dependency — install via repo |
| Active debrid account (Real-Debrid etc.) | Yes | Configure in resolveurl settings |
| TMDB API key | No | Optional — enables movie backdrop art |

Wrestling is accessible without IPTV credentials. Movies and Series will prompt for credentials if not set.

---

## Installation

Install as a zip file via Kodi's Add-on Manager:

1. Settings → Add-ons → Install from zip file
2. Select `plugin_video_echoondemand-2_5_0.zip`
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

No Wrestling-specific settings are exposed. The feed URL is hardcoded with a fallback in code; see the architecture notes below if it ever needs changing.

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

Content comes from a remote MicroJen XML/JSON feed at `mylostsoulspace.co.uk`. The feed describes a directory tree of wrestling shows and events. Each leaf item contains one or more candidate links (magnet URIs and/or direct HTTP hosters).

At play time, `resolve_best_link()` in `wrestling.py` tries each link in order:
1. **Debrid** — `resolveurl.HostedMediaFile(link).resolve()`. First successful result wins.
2. **Direct video** — any link with a recognisable video extension (`.mp4`, `.mkv`, `.m3u8`, etc.)
3. **HTTP fallback** — first HTTP URL, played directly by Kodi

The user sees none of this — it either plays or shows an error notification.

---

## File Structure

```
plugin.video.echoondemand/
  addon.xml                  Kodi metadata, dependencies (includes resolveurl)
  default.py                 Entire plugin — routing, views, IPTV data layer
  icon.png                   Addon icon (256x256)
  fanart.jpg                 Addon background fanart
  resources/
    settings.xml             Four user-facing settings
    __init__.py
    lib/
      __init__.py
      wrestling.py           Wrestling data layer (fetch, parse, resolve)
    images/
      genres/                PNG icons for IPTV genre categories (256x256 RGBA)
        Action.png
        Comedy.png
        Wrestling.png        Available for future use; root currently uses ADDON_ICON
        ... (40+ files)
```

---

## Architecture

### default.py

A single-file plugin following Kodi's standard pattern:

- `router(paramstring)` — reads URL params, dispatches to the right view function
- One `list_*` function per directory view, one `play_*` function per playable type
- Cache uses `{ts, payload}` JSON files in the addon profile directory
- TMDB fanart is a separate persistent JSON cache, populated lazily at play time

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
| Wrestling (any level) | `files` | No metadata to display; info panel suppressed |

### wrestling.py

Pure data layer — no Kodi UI calls. Importable and testable in isolation.

Three logical sections:
1. **Cache** — `cache_load()` / `cache_save()` — raw feed text keyed by sanitised URL
2. **Parse** — `parse_feed()` dispatches to `parse_xml()` or `parse_json()`. XML parser has four recovery passes including a per-item regex fallback for broken feeds.
3. **Resolve** — `resolve_best_link()` — debrid first, direct video second, HTTP fallback third

### Cache system

All cache files live in `xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))`.

| File pattern | TTL | Contents |
|---|---|---|
| `movie_cats.json` | 1 hour | Movie genre list from API |
| `series_cats.json` | 1 hour | Series genre list from API |
| `movies_{cat_id}.json` | 30 min | Stream list for one movie category |
| `series_{cat_id}.json` | 30 min | Stream list for one series category |
| `seriesinfo_{id}.json` | 1 hour | Full season/episode data for one series |
| `tmdb_fanart.json` | Permanent | TMDB backdrop URL cache, key = `name\|year` |
| `wr_{url_hash}.json` | 30 min | Wrestling feed text, managed by wrestling.py |

"Refresh / Clear Cache" in the root menu deletes all `*.json` files from the profile directory. This clears IPTV cache, Wrestling cache, and TMDB cache simultaneously.

---

## Adding a New Content Section

The Wrestling section is the template. To add a new source (e.g., sports replays, anime):

1. **Create `resources/lib/{source}.py`** — same structure as `wrestling.py`: fetch, parse, resolve. No Kodi UI calls.
2. **Add a root entry in `list_root()`** — follow the Movies/Series/Wrestling pattern.
3. **Add `list_{source}` and `play_{source}` functions** in `default.py` — follow `list_wr` / `play_wr` exactly.
4. **Wire up the router** — add `elif mode == '{source}_list':` and `elif mode == '{source}_play':` to `router()`.
5. **Add URL params to router** — add param extraction at the top of `router()`.

No changes to `addon.xml` unless the new source requires an additional Kodi module dependency.

---

## Skin Notes (Aeon Nox Silvo)

The addon was developed and tested against Aeon Nox Silvo. Two skin files were modified alongside the addon to suppress unwanted info panels:

- `MyVideoNav.xml` — ghost control reference removed; info panel conditions added
- `View_50_List.xml` — right-side info panel suppressed when `Container.Content(files)` and `Container.PluginName` match

If the skin is updated or replaced, the `setContent()` values above may need revisiting. The most visible symptom of a mismatch is an empty info panel on the right side of a genre category list.

---

## Troubleshooting

**"No items found in this section" on a Wrestling sub-feed**  
Clear the cache (root menu → Refresh / Clear Cache) and retry. If it persists, check the Kodi log for `[EchoOD/Wrestling] PARSE FAILED` — the log line includes the first 300 characters of the raw feed for diagnosis.

**Wrestling item plays blank / "Could not resolve stream"**  
Check the Kodi log for `[EchoOD/Wrestling] resolve_best_link` lines. These are logged at INFO level (no debug mode needed). They show each candidate URL, whether resolveurl accepted it, and which pass was used. Most likely cause: debrid account not configured in resolveurl settings, or the hoster is not supported.

**Movies/Series show "Please enter credentials" on every open**  
Enter username and password in Settings (addon settings, not Kodi system settings). The server address is hardcoded — only credentials are user-configurable.

**Kodi hangs loading a category (spinning indefinitely)**  
Fixed in v2.5.0. All error paths now call `endOfDirectory(succeeded=False)`. If this occurs on v2.5.0+, it is a new error path that was missed — check the Kodi log for `[EchoOD]` entries around the time of the hang.
