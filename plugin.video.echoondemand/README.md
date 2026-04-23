# Echo OnDemand
**Kodi plugin for browsing and playing VOD content from an Xtream Codes IPTV service.**

Version 1.3.0 · Kodi Omega (v21) · Python 3 · Provider: Echo-Storm

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

The addon does not require any repository. It installs standalone from the zip.

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
4. Backdrop art is fetched during the pre-buffer window the first time each movie is played, then cached permanently — zero impact on list loading

---

## Features

### Movies
- Browse by genre category with bundled colour-coded genre icons
- Metadata: title, year, rating, plot, cast, director, genre, runtime — all sourced from the IPTV provider API
- Context menu: Mark as Watched, Movie Information, Add to Queue
- Sort by: Title, Year, Rating
- TMDB backdrop art (optional, populated lazily at play time)

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
- Cache cleared via **Refresh / Clear Cache** in the root menu (also clears TMDB fanart cache)
- Pre-buffer: stream starts, pauses silently for configured seconds, resumes automatically
- 40 bundled genre icons, colour-coded by type (Action=red, Comedy=yellow, Horror=dark red, Sci-Fi=blue, etc.)
- Series fanart (backdrop_path) carries through to season and episode views
- Movies: TMDB backdrop if cached, otherwise addon default fanart
- Fully Omega-compatible: InfoTagVideo API, xbmc.Actor cast objects, getCondVisibility for pause detection

---

## Companion Skin Edit (MyVideoNav.xml)

A matching edit to `MyVideoNav.xml` in the Aeon Nox Silvo EchoStorm Edition skin adds a **plot synopsis overlay** above the poster panel, visible only when browsing Echo OnDemand.

Features of the overlay:
- Locked to `plugin.video.echoondemand` via `Container.PluginName` — does not appear in any other addon
- Positioned above the poster in the clear space below the topbar (1920×1080 virtual coordinates)
- 82% opaque dark backing, white `font12` text
- Auto-scrolls through long synopses: 1.5s delay, 4s scroll, 5.5s loop
- Visible only for movies, TV shows, and episodes with a non-empty plot

The `ScriptHelperFlags` grouplist was also widened from 340px to 480px in the same file to give the rating helper scripts (RT, Audience Score, TMDB) room to display simultaneously without displacement.

---

## Architecture

```
plugin.video.echoondemand/
├── default.py              # Main plugin — routing, views, API, cache, TMDB
├── addon.xml               # Addon manifest with <assets> block
├── fanart.jpg              # Default background (film reel / fantasy landscape)
├── icon.png                # Addon icon (256×256)
├── README.md               # This file
└── resources/
    ├── settings.xml        # Settings: username, password, buffer_secs, tmdb_api_key
    └── images/
        └── genres/         # 40 bundled genre icons (PNG, 256×256, Poppins Bold)
```

### Routing

| mode | Parameters | Action |
|---|---|---|
| *(none)* | — | Root view (Movies / Series / Refresh) |
| `movie_cats` | — | Movie genre category list |
| `movies` | `cat_id` | Movie list for a genre |
| `play_movie` | `vod_id`, `ext`, `vod_name`, `vod_year` | Resolve and play a movie |
| `series_cats` | — | Series genre category list |
| `series` | `cat_id` | Series list for a genre |
| `seasons` | `series_id` | Season list for a series |
| `episodes` | `series_id`, `season` | Episode list for a season |
| `play_episode` | `ep_id`, `ext` | Resolve and play an episode |
| `refresh` | — | Clear all cache, return to root |

### Cache files (addon profile directory)

| File | TTL | Contents |
|---|---|---|
| `movie_cats.json` | 1 hour | Movie genre category list |
| `series_cats.json` | 1 hour | Series genre category list |
| `movies_{cat_id}.json` | 30 min | Movie list for one genre |
| `series_{cat_id}.json` | 30 min | Series list for one genre |
| `seriesinfo_{id}.json` | 1 hour | Full season/episode data for one series |
| `tmdb_fanart.json` | permanent | TMDB backdrop URLs keyed by `name\|year` |

### Stream URL formats
```
Movie:   https://{server}/movie/{user}/{pass}/{vod_id}.{ext}
Episode: https://{server}/series/{user}/{pass}/{episode_id}.{ext}
```

### Pre-buffer implementation
After `setResolvedUrl`, the plugin process stays alive until Python exits. The buffer function polls `player.isPlaying()` every 250ms (up to 12s), pauses when playback starts, waits the configured seconds, then resumes using `xbmc.getCondVisibility('Player.Paused')` — `xbmc.Player.isPaused()` does not exist in Kodi Omega.

### TMDB fanart implementation
TMDB fanart is fetched during the pre-buffer window (absorbed into existing wait time) using `/search/movie?query={name}&year={year}`. Results are cached in `tmdb_fanart.json` keyed by `name|year`. The cache is read at list load time (local JSON read only, no API calls). Movies without a cached backdrop use the addon's default fanart.

---

## Known Limitations

- **Movie backdrop art**: This provider's `get_vod_streams` response does not include any backdrop/fanart field. Movie backgrounds use TMDB cache if configured, otherwise addon default fanart.
- **Series without backdrop**: Falls back to addon default fanart.
- **TMDB cache fills gradually**: Only populated when movies are played. No batch pre-fetch to avoid blocking list loads.
- **Genre icons**: Bundled for 40 common genres. Unknown genres fall back to `DefaultGenre.png`. New genre icons can be added to `resources/images/genres/` as `{genre_name}.png`.
- **Media flags** (resolution, codec, audio): Only appear for items that have been played at least once — Kodi stores these from actual stream playback.

---

## Changelog

### 1.3.0
- Final fanart confirmed (film reel / fantasy landscape)
- README fully updated
- Version milestone: feature-complete for initial release

### 1.2.x
- TMDB fanart cache bug fixed — fanart was computed but not passed to make_art()
- Movie and series runtime added via `episode_run_time` → `tag.setDuration()`
- TMDB cache loading no longer gated on key presence (always reads local cache)
- Companion skin edit: plot synopsis overlay in MyVideoNav.xml
- Companion skin edit: ScriptHelperFlags grouplist widened 340→480px for full rating display

### 1.2.0
- New default fanart (film reel / fantasy landscape, less busy than original)
- Movie fanart reverted to clean ADDON_FANART fallback (poster-as-background caused severe cropping)
- README added

### 1.1.x
- TMDB fanart integration (optional, lazy cache populated at play time)
- Movie metadata enriched: cast, director, genre now set via InfoTagVideo
- Series director added to InfoTagVideo
- Series fanart carried through season and episode views
- landscape art type tested and confirmed unsupported by skin (reverted)
- Diagnostic logging added and removed after confirming provider field set

### 1.1.0
- Full audit: make_art fanart fallback restored (fixed movies losing background after 1.0.9 regression)
- ADDON_PATH module constant added (eliminates repeated translatePath calls in genre icon lookup)
- Docstring version corrected

### 1.0.x
- 40 bundled genre icons (colour-coded, Poppins Bold labels, adaptive bar height)
- isPaused() → xbmc.getCondVisibility('Player.Paused') (Omega compatibility)
- Pre-buffer default raised to 5s, notification toast removed (silent buffer)
- Icon and fanart path resolution fixed (assets block in addon.xml, path from addon root)
- Root emoji labels replaced with plain text (skin font compatibility)
- Series fanart propagation to seasons/episodes
- Context menus: Mark as Watched, Information, Queue
- offscreen=True on all ListItem construction
- SpecialSort=bottom on Refresh entry
- setInfo → getVideoInfoTag / InfoTagVideo API throughout (Omega)
- Cast: list[str] → list[xbmc.Actor] (Omega)
- xbmc.gui version corrected for Omega (5.17.0)

### 1.0.0
- Initial release: Movies by genre, Series with season/episode navigation, local caching, pre-buffer, bundled fanart/icon
