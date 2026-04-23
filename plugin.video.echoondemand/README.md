# Echo OnDemand
**Kodi plugin for browsing and playing VOD content from an Xtream Codes IPTV service.**

Version 2.0.0 · Kodi Omega (v21) · Python 3 · Provider: Echo-Storm

---

## Requirements

- Kodi 20 (Nexus) or 21 (Omega) — developed and tested on Omega v21.3
- An active Xtream Codes-compatible IPTV subscription
- The service must support `player_api.php` (standard Xtream Codes API)

---

## Installation

1. Download `plugin.video.echoondemand-x.x.x.zip`
2. In Kodi: **Add-ons → Install from zip file** → select the zip
3. Open the addon and go to **Settings**
4. Enter your IPTV **Username** and **Password**
5. Browse Movies or Series

The addon installs standalone from the zip — no repository required.

---

## Settings

| Setting | Description | Default |
|---|---|---|
| Username | Your Xtream Codes service username | — |
| Password | Your Xtream Codes service password | — |
| Pre-buffer seconds | Pause after stream starts before playing. Helps with unstable streams. Set to 0 to disable. | 5 |
| TMDB API Key | Optional. Free key from themoviedb.org. Enables movie backdrop art fetched and cached at play time. | — |

### Getting a TMDB API key (optional)
1. Register at [themoviedb.org](https://www.themoviedb.org)
2. Settings → API → Request an API key (v3 auth) — free, takes 2 minutes
3. Paste the key into addon Settings
4. Backdrop art is fetched after the pre-buffer completes the first time each movie is played, then cached permanently — zero impact on list loading speed

---

## Features

### Movies
- Browse by genre category with 40 bundled colour-coded genre icons
- Metadata: title, year, rating, plot, cast, director, genre, runtime
- Context menu: Mark as Watched, Movie Information, Add to Queue
- Sort by: Title, Year, Rating
- Optional TMDB backdrop art (lazy-cached at play time)

### Series
- Browse by genre category
- Full season and episode navigation
- Series backdrop art carried through to season and episode views
- Metadata: title, year, rating, plot, cast, director, genre, episode runtime
- Episode metadata: title, plot, duration, episode/season numbers
- Context menu: Mark as Watched / Episode Information / Add to Queue (episodes), Show Information (series)
- Sort by: Title, Year, Rating (series); Episode number (episodes)

### General
- All results cached locally — categories 1 hour, stream lists 30 min, series info 1 hour
- Cache cleared via **Refresh / Clear Cache** in the root menu
- Pre-buffer: stream starts, pauses silently for configured seconds, resumes automatically
- Fully Omega-compatible: InfoTagVideo API, `xbmc.Actor` cast objects, `getCondVisibility` for pause detection

---

## Companion Skin Edits (Aeon Nox Silvo — EchoStorm Edition)

Three skin XML files carry companion edits, each scoped to this addon via `Container.PluginName(plugin.video.echoondemand)`. No other addon or library view is affected.

### MyVideoNav.xml

**Plot synopsis overlay**
Displays a scrolling plot synopsis above the poster panel when browsing movie lists and series/season folders. Not shown on the episode list view, which already provides a full built-in info panel.

- Dark backing at 82% opacity, white `font12` text
- Auto-scrolls: 1.5 s delay, 4 s scroll, 5.5 s loop
- Active for `movies` and `tvshows` content only

**InfoPanel suppression for genre category views**
The skin's InfoPanel overlay (views 52, 53, 57, 58, 59) is suppressed when browsing genre category lists (`Content(files)`). Prevents the genre badge being upscaled into the overlay artwork slot.

**ScriptHelperFlags grouplist**
Widened from 340 px to 480 px so RT, Audience Score, TMDB, and IMDb rating helpers display simultaneously without displacement.

### View_50_List.xml

**Right-panel suppression for genre category views**
Added a `Container.PluginName` + `Container.Content(files)` visibility condition to both the VideoList and SlimVideoList right-panel groups. When browsing genre categories in this addon, the right panel is suppressed entirely — preventing the genre icon badge from rendering as a large poster. All other addons and content types are unaffected.

**Duplicate label removed**
A copy-paste duplicate `IsCollection` label in the VideoList movies `itemlayout` was removed (the `focusedlayout` correctly had only one).

---

## Architecture

```
plugin.video.echoondemand/
├── default.py              # Main plugin — routing, views, API, cache, TMDB
├── addon.xml               # Addon manifest with <assets> block
├── fanart.jpg              # Default background
├── icon.png                # Addon icon (512×512)
├── README.md               # This file
└── resources/
    ├── settings.xml        # Settings: username, password, buffer_secs, tmdb_api_key
    └── images/
        └── genres/         # 40 bundled genre icons (PNG, Poppins Bold)
```

### Routing

| mode | Parameters | Action |
|---|---|---|
| *(none)* | — | Root view (Movies / Series / Refresh) |
| `movie_cats` | — | Movie genre category list |
| `movies` | `cat_id`, `cat_name` | Movie list for a genre |
| `play_movie` | `vod_id`, `ext`, `vod_name`, `vod_year` | Resolve and play a movie |
| `series_cats` | — | Series genre category list |
| `series` | `cat_id`, `cat_name` | Series list for a genre |
| `seasons` | `series_id` | Season list for a series |
| `episodes` | `series_id`, `season` | Episode list for a season |
| `play_episode` | `ep_id`, `ext` | Resolve and play an episode |
| `refresh` | — | Clear all cache, return to root |

### Content types by view

| View | Content type | Rationale |
|---|---|---|
| Root | `addons` | Suppresses empty episode info panel; renders addon icon cleanly in poster slot |
| Movie categories | `files` | Suppresses skin right-panel — lets genre badge stay as a small list icon |
| Series categories | `files` | Same |
| Movie list | `movies` | Standard media library type |
| Series list | `tvshows` | Standard media library type |
| Season list | `seasons` | Correct Kodi type for season-level views |
| Episode list | `episodes` | Standard media library type |

### Cache files (addon profile directory)

| File | TTL | Contents |
|---|---|---|
| `movie_cats.json` | 1 hour | Movie genre category list |
| `series_cats.json` | 1 hour | Series genre category list |
| `movies_{cat_id}.json` | 30 min | Movie list for one genre |
| `series_{cat_id}.json` | 30 min | Series list for one genre |
| `seriesinfo_{id}.json` | 1 hour | Full season/episode data for one series |
| `tmdb_fanart.json` | permanent (no TTL) | TMDB backdrop URLs keyed by `name\|year` |

Refresh / Clear Cache deletes all of the above including the TMDB cache.

### Stream URL formats
```
Movie:   https://{server}/movie/{user}/{pass}/{vod_id}.{ext}
Episode: https://{server}/series/{user}/{pass}/{episode_id}.{ext}
```

### Pre-buffer implementation
After `setResolvedUrl`, the plugin process stays alive until Python exits. `_apply_buffer` polls `player.isPlaying()` every 250 ms (up to 12 s), pauses on playback start, sleeps silently for the configured seconds, then resumes via `xbmc.getCondVisibility('Player.Paused')` — `xbmc.Player.isPaused()` does not exist in Kodi Omega.

### TMDB fanart implementation
TMDB fanart is fetched after `_apply_buffer` completes in `play_movie`. The plugin process remains alive after `setResolvedUrl` returns, so the network call runs while the stream is already playing — zero perceived impact on buffer length. Results are cached in `tmdb_fanart.json` keyed by `name|year` and read at list load time (local JSON only, no API calls). Movies without a cached backdrop fall back to the addon's default fanart.

---

## Known Limitations

- **Movie backdrop art**: The provider's `get_vod_streams` response includes no backdrop/fanart field. Movie backgrounds use the TMDB cache if configured, otherwise the addon default fanart.
- **Series without backdrop**: Falls back to addon default fanart.
- **TMDB cache fills gradually**: Populated only when movies are played. No batch pre-fetch, to avoid blocking list loads.
- **Genre icons**: Bundled for 40 common genres. Unknown genres fall back to `DefaultGenre.png`. Additional icons can be dropped into `resources/images/genres/` as `{genre_name}.png`.
- **Media flags** (resolution, codec, audio): Only appear after an item has been played — Kodi populates these from actual stream playback data.

---

## Changelog

### 2.0.0
- Root view: `setContent` changed `'videos'` → `'addons'` — eliminates empty info panel below addon icon on the root menu. The `videos` type triggered the skin's episode info panel which rendered the icon at the top and left a blank text box below it; `addons` uses the simple poster panel instead
- Unused `URLError` import removed (dead code — all callers use `except Exception`)
- Stale "icons restored" comment cleaned up in `list_series_categories`
- Skin — `MyVideoNav.xml`: plot synopsis overlay restricted to `movies` + `tvshows`; removed from `episodes` where the skin already provides a built-in full info panel
- Skin — `MyVideoNav.xml`: InfoPanel suppression condition added for genre category views
- Skin — `MyVideoNav.xml`: ghost `Control.GetLabel(4421)` reference removed (control never defined; dead code from a previous skin revision)
- Skin — `View_50_List.xml`: right-panel suppression added to VideoList and SlimVideoList for genre category views
- Skin — `View_50_List.xml`: duplicate `IsCollection` label removed from VideoList movies `itemlayout`
- Icon updated to 512×512

### 1.3.1
- `credentials_ok()` guarded in `list_movie_categories` / `list_series_categories` — deep links now show a proper credentials dialog instead of a raw API error
- `cat_name` threaded through URL params; `list_movies` / `list_series` call `setPluginCategory` with the actual genre name for correct breadcrumb display
- `list_series`: empty-list guard added to match `list_movies` behaviour
- `list_episodes`: empty-episode-list guard added
- `list_seasons`: `setContent` changed `'tvshows'` → `'seasons'` (correct Kodi type)
- Refresh item: `isFolder` changed `False` → `True` (was misusing the playable-item contract)
- `play_movie`: TMDB fetch moved to after `_apply_buffer` — runs while stream is already playing
- `_apply_buffer` docstring: stale "show notification toast" step removed
- Category list items: `Content('files')` drives right-panel suppression at skin level

### 1.2.x
- TMDB fanart cache bug fixed — fanart was computed but not passed to `make_art()`
- Movie and series runtime added via `episode_run_time` → `tag.setDuration()`
- TMDB cache loading no longer gated on key presence
- Companion skin edit: plot synopsis overlay in `MyVideoNav.xml`
- Companion skin edit: ScriptHelperFlags grouplist widened 340 → 480 px

### 1.2.0
- New default fanart
- Movie fanart reverted to clean `ADDON_FANART` fallback

### 1.1.x
- TMDB fanart integration (optional, lazy cache populated at play time)
- Movie metadata enriched: cast, director, genre via InfoTagVideo
- Series director added to InfoTagVideo
- Series fanart carried through to season and episode views

### 1.1.0
- Full audit: `make_art` fanart fallback restored
- `ADDON_PATH` module constant added (eliminates repeated `translatePath` calls)

### 1.0.x
- 40 bundled genre icons (colour-coded, Poppins Bold labels)
- `isPaused()` → `xbmc.getCondVisibility('Player.Paused')` (Omega compatibility)
- Pre-buffer default raised to 5 s; notification toast removed (silent buffer)
- Icon and fanart path resolution fixed (`<assets>` block in `addon.xml`)
- Root emoji labels replaced with plain text (skin font compatibility)
- Series fanart propagation to seasons/episodes
- Context menus: Mark as Watched, Information, Queue
- `offscreen=True` on all `ListItem` construction
- `SpecialSort=bottom` on Refresh entry
- `setInfo` → `getVideoInfoTag` / InfoTagVideo API throughout (Omega)
- Cast: `list[str]` → `list[xbmc.Actor]` (Omega)
- `xbmc.gui` version corrected for Omega (5.17.0)

### 1.0.0
- Initial release: Movies by genre, Series with full season/episode navigation, local caching, pre-buffer, bundled fanart/icon
