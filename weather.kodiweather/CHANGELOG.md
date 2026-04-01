# Changelog

All notable changes to weather.kodiweather.

## [2.4.2] - 2026-03-26

### Added
- **Fanart folder mapping** — Redirects clone condition codes to master folders, enabling resource.images.weatherfanart.echo to eliminate ~1.2GB of duplicate images
- **config.py**: Added `map_fanart` dict mapping 50 Yahoo weather codes to 17 master folders
- **config.py**: Added `get_fanart_folder()` helper function

### Changed
- **utils.py**: All `fanartcode` property assignments now use `config.get_fanart_folder()` wrapper (6 locations)
- **utils.py**: `code` unit handler (line 264) now applies fanart folder mapping

### Technical Notes
- Clone codes redirect to masters: 4→3, 6/7/8/10/18→5, 14/15/16/41/42/43/46→13, etc.
- Icons still use original Yahoo codes (no change to outlookicon paths)
- Requires corresponding cleanup of resource.images.weatherfanart.echo clone folders to reclaim space

## [2.4.1] - 2026-03-21

### Fixed
- **config.py**: NWS alerts 400 error — api.weather.gov no longer accepts `limit` parameter. Removed `&limit=10` from noaalerts URL.

## [2.4.0] - 2026-03-21

### Changed
- **MAJOR: Radar source migrated from RainViewer to IEM NEXRAD** — RainViewer restricted free API (Jan 2026), locked to single color scheme. IEM provides authentic NEXRAD green/yellow/red colors with no restrictions.
- **config.py**: Replaced RainViewer URLs with IEM TMS endpoint
- **config.py**: Added `iem_frame_offsets` list for fixed frame timing
- **config.py**: Removed `map_radarcolor` dict (no longer applicable)
- **config.py**: Removed `addon.radarcolor` setting
- **api.py**: Replaced `getrvindex()` with `getiemframes()` — no API query needed
- **api.py**: Updated `getmap()` for IEM with server load balancing (mesonet1/2/3)
- **weather.py**: Updated radar download logic for IEM fixed offsets
- **weather.py**: Changed folder name `rvradar` → `iemradar`
- **weather.py**: Updated provider attribution
- **monitor.py**: Removed radarcolor change detection (no longer needed)
- **settings.xml**: Removed radarcolor setting dropdown
- **settings.xml**: Changed `maprvradar` → `mapiemradar`
- **strings.po**: Removed #32520-#32529 (radar color scheme strings)
- **strings.po**: Updated addon description for IEM

### Removed
- Radar color scheme selection (NEXRAD colors baked into IEM tiles)
- Satellite layer (RainViewer free API no longer provides satellite data)

### Technical Notes
- IEM provides 12 frames (current + 5/10/15/20/25/30/35/40/45/50/55 min ago)
- All frames re-download each hourly cycle (offsets are relative to "now")
- Server load balancing across mesonet1/2/3.agron.iastate.edu

## [2.3.2] - 2026-03-21

### Fixed
- **monitor.py**: Radar color scheme change now actually works — cached frames are deleted when color changes, forcing re-download with new color scheme.

## [2.3.1] - 2026-03-21

### Fixed
- **weather.py**: Cache-timestamp mismatch bug — clearing cache without clearing settings caused addon to skip downloads (showed 32°F/empty data). Now checks if cache files exist before trusting timestamps.

## [2.3.0] - 2026-03-20

### Added
- **Radar Color Scheme Selection**: Choose from 9 RainViewer color schemes (Original, Universal Blue, TITAN, The Weather Channel, Meteored, NEXRAD Level III, Rainbow, Dark Sky, Color-coded)
- **Base Map Provider Selection**: Choose from 7 tile providers (OpenStreetMap, CartoDB Dark, CartoDB Dark No Labels, CartoDB Light, CartoDB Light No Labels, CartoDB Voyager, OpenTopoMap)
- **settings.xml**: New dropdowns in Maps category for Map Style and Radar Color Scheme
- **strings.po**: Added localization strings 32510-32529

### Changed
- **config.py**: Added `map_providers` dict for tile provider URLs
- **config.py**: Added `map_radarcolor` dict for color scheme mapping
- **config.py**: RainViewer URL now uses placeholder for color scheme
- **api.py**: `getmap()` now uses selected map provider and radar color
- **monitor.py**: Detects provider/color changes and triggers re-download

## [2.2.12] - 2026-03-20

### Fixed
- **MyWeather.xml**: Added `<randomize>false</randomize>` to multiimage — frames were playing out of sequence

## [2.2.11] - 2026-03-20

### Changed
- **api.py**: Moved timestamp 70px more to the left for better positioning

## [2.2.10] - 2026-03-20

### Changed
- **api.py**: Timestamp position fine-tuned (left 50px, down 50px)
- **MyWeather.xml**: Removed redundant "Radar" label from map display

## [2.2.9] - 2026-03-20

### Changed
- **api.py**: Moved timestamp to y=456 (60% down image) to survive fullscreen scaling/crop

### Notes
- Radar timestamp now visible at all zoom levels and fullscreen
- Known issue: radar appears "anemic" — fix by changing `colordiffuse` in MyWeather.xml from `70FFFFFF` to `DDFFFFFF`

## [2.2.8] - 2026-03-20

### Changed
- **api.py**: Moved timestamp up and left 100px more (still getting cut off)

## [2.2.7] - 2026-03-20

### Changed
- **api.py**: Moved timestamp up 30px to avoid cutoff at high zoom levels

## [2.2.6] - 2026-03-20

### Fixed
- **api.py**: Simplified timestamp rendering — removed textbbox/alpha_composite that required newer Pillow
- Now uses simple shadow (black offset) + white text, fixed position bottom-right

## [2.2.5] - 2026-03-20

### Fixed
- **api.py**: Tile paste bug — fallback tiles weren't being pasted (was in `else` block)
- **api.py**: Wrapped timestamp burning in try/except to prevent crashes on older Pillow
- **weather.py**: Removed trailing slash from LayerPath property

### Added
- Debug logging for radar frame saves ("Saved radar frame" / "Failed to save")

## [2.2.4] - 2026-03-20

### Fixed
- **weather.py**: Radar menu now shows even if radar frames haven't downloaded yet
  - OSM base map check is now independent from radar frame check
  - Previously, menu was hidden if subfolder was empty (broke on cache structure change)

## [2.2.3] - 2026-03-20

### Changed
- **api.py**: Radar frames now have timestamp burned into image (bottom-right, semi-transparent background)
- **MyWeather.xml**: Removed static time label — each frame now shows its own time as animation plays

### Notes
- Clear your radar cache to regenerate frames with timestamps
- Timestamp uses your Kodi date/time format settings

## [2.2.2] - 2026-03-20

### Added
- Alert timing sliders now visible in Settings → Notifications
  - **Interval**: How often to check/show alerts (5-60 min, default 30)
  - **Duration**: How long notification displays (5-60 sec, default 15)

### Changed
- Moved `alert_interval` and `alert_duration` from hidden category to Notifications
- Sliders only visible when NWS Alerts are enabled

## [2.2.1] - 2026-03-20

### Changed
- **MyWeather.xml**: Radar label now shows "Radar - Mar 20 2:30 PM" instead of just "Radar"

## [2.2.0] - 2026-03-20

### Added
- New window property `Map.{index}.LayerPath` — folder path for multiimage animation
- Skin-side radar animation via Kodi's `<multiimage>` control

### Changed
- **api.py**: Radar frames now save to subfolder (`{cache}/{locid}/rvradar/`) instead of flat structure
- **weather.py**: Updated `getmap()` and `setother()` for subfolder paths
- **MyWeather.xml**: Replaced static radar image with animated `<multiimage>` (500ms/frame, 2s pause, loop)

### Notes
- Radar animation plays automatically when viewing the Radar tab
- ~13 frames covering ~65 minutes of history
- Old flat-structure cache files (`rvradar_*.png`) will be ignored — clean install recommended

## [2.1.0] - 2026-03-20

### Added
- **Radar animation**: Addon now downloads all available RainViewer frames (~13 frames, 10-minute intervals)
- New window property `Map.{index}.FrameCount` for skins to use in animation loops
- Smart caching: Only downloads new frames, skips existing ones

### Changed
- **api.py**: `getrvindex()` now returns all frames instead of just the latest
- **weather.py**: `getmap()` iterates over all available frames for RV layers

### Notes
- Skin-side animation requires MyWeather.xml changes to cycle through `Map.1.Layer.0` through `Map.1.Layer.{FrameCount-1}`
- `maphistory` setting controls max frames retained (default 24)

## [2.0.0] - 2026-03-20

### Fixed
- **conv.py**: uvindex conversion used wrong function (`temp()` instead of `dp()`) — would have caused type errors in graph alerts
- **api.py**: Missing f-string prefix in location search error log — `locid` wasn't interpolating
- **utils.py**: `mode()` calls could throw `StatisticsError` on empty or uniform data lists (root cause of Daily.7 timeofday crashes) — added try/except with `max()` fallback
- **config.py**: Module-level `maxdays` setting read could fail before `init()` — added try/except with default fallback

### Changed
- Branch: 2.0.x series begins
- Import: Added `StatisticsError` to statistics imports in utils.py

## [1.0.52] - 2026-03-20

### Changed
- Logging settings (Debug, Verbose) moved to new "Logging" tab (category 9)
- Advanced category hidden — icons, forecast days, alert timing, colors all use defaults

## [1.0.51] - 2026-03-20

### Removed
- Optional weather icon sets (default, metno, weathermap, wmo) — saves ~6.9 MB
- Skin uses Kodi's built-in `resource.images.weathericons.default` instead

### Changed
- Icons setting hidden in Advanced category

## [1.0.50] - 2026-03-20

### Changed
- Satellite map setting (`maprvsatellite`) hidden and disabled — RainViewer free API no longer returns satellite data

### Added
- README.md for GitHub
- HANDOFF.md session documentation

## [1.0.49] - 2026-03-20

### Changed
- Settings reorganization: new "Notifications" category (id=8) for NWS Alerts
- NWS Alerts moved from hidden Experimental category to visible Notifications tab
- Location 5 removed entirely (group and all storage settings)
- `explocations` and `enablehour` settings hidden (compatibility, not removed)

## [1.0.48] - 2026-03-20

### Fixed
- NWS Alerts label bug in strings.po

## [1.0.47] - 2026-03-20

### Fixed
- Overview screen layout issues in MyWeather.xml

## [1.0.46] - 2026-03-20

### Changed
- Settings cleanup: Units, Weather Alerts, Air Quality, Pollen categories hidden
- US defaults hardcoded, no user configuration needed

## [1.0.45] - 2026-03-20

### Added
- Hourly precipitation percentage display (Hourly.N.Precipitation)
- Consistent precipitation placement on row 3 for both daily and hourly panels

## [1.0.44] - 2026-03-20

### Added
- Daily precipitation percentage display (Daily.N.Precipitation)
- 7-day forecast layout redesign matching 24-hour style

## [1.0.43] - 2026-03-20

### Fixed
- Temperature double-conversion bug — temps were being converted twice on cached reads

## [1.0.42] - 2026-03-19

### Changed
- Minor refinements (superseded)

## [1.0.41] - 2026-03-19

### Changed
- Minor refinements (superseded)

## [1.0.40] - 2026-03-19

### Fixed
- Reverted conv.temp() to upstream logic — kodi=True routes through getRegion('tempunit')
- Architecture fix: unittemp default changed to 'app' (follows Kodi regional setting)

### Changed
- Encoding fix retained from 1.0.39
- or-fallbacks retained in config.py

## [1.0.39] - 2026-03-19

### Fixed
- settings.xml encoding bug — utils.settings() now uses `encoding='utf-8'`
- Root cause: Windows cp1252 decoded UTF-8 degree symbol (°) as Â°, breaking unit detection

## [1.0.38] - 2026-03-19

### Added
- Diagnostic logging to confirm encoding bug

## [1.0.37] - 2026-03-19

### Added
- or-fallback defaults for all unit settings in config.py
- addon.temp or '°F', addon.speed or 'mph', addon.precip or 'in', etc.

## [1.0.36] - 2026-03-19

### Fixed
- min()/max() shadowing crash in setmulti
- Bounds cap: `end = idx + max if idx + max <= available else available`

## [1.0.35] - 2026-03-19

### Changed
- All US unit defaults complete in settings.xml

## [1.0.34] - 2026-03-19

### Changed
- settings.xml US defaults
- setmulti bounds fix (had crash, superseded)

## [1.0.33] - 2026-03-19

### Removed
- EU pollen species from API URL and map entries (alder, birch, mugwort, olive)
- These return null for US locations and generated ~900 log writes per cycle

### Changed
- conv.temp() rewrite (later reverted in 1.0.40)
- US unit defaults added

## [1.0.32] - 2026-03-19

### Fixed
- Removed 7 currentkodi/dailykodi map overwrite entries from config.py
- These were overwriting correctly converted °F temps with raw Celsius

## [1.0.31] - 2026-03-19

### Changed
- Version bump from prior session zip

## [1.0.30] - 2026-03-18

### Changed
- **Addon renamed**: weather.openmeteo → weather.kodiweather
- **Display name**: Open-Meteo → Kodi Weather
- **Provider**: forynski → Echo-Storm
- **Source URL**: Updated to https://github.com/Echo-Storm
- **GeoIP provider**: api.openht.org → ip-api.com
- **User-agent**: Updated to weather.kodiweather

### Removed
- All non-en_GB language files (12 languages removed)
- All skin-mode code paths (currentskin, hourlyskin, dailyskin)
- addon.api, addon.skin, addon.full, addon.mode attributes
- winprop(openmeteo) read — not used by Aeon Nox Silvo
- 5 non-existent screenshot asset references from addon.xml
- weather.gc.ca references from provider strings

### Fixed
- getloc() GeoIP field names updated for ip-api.com (region_name→regionName, country_code→countryCode)
- getloc() matching bug — loop was checking `location` instead of `item`
- Country-only fallback changed from `if` to `elif` to prevent stealing break

### Notes
- Addon is now single-path codebase with no feature flags
- currentkodi and dailykodi map entries retained (fire on mode==kodi)

---

## Pre-Fork History

Based on weather.openmeteo by forynski (upstream: github.com/bkury/weather.openmeteo)
