# Changelog

All notable changes to weather.kodiweather.

## [2.4.7] - 2026-04-24

### Fixed — Home screen background stability

- **lib/config.py**: Added `get_fanartbg(code, locid)` — picks one image from the fanart resource folder when the weather code changes and holds it for the session. Previously the skin's `multiimage` control received a folder URI and cycled through every image in it on a timer, causing constant background changes unrelated to actual weather updates.
- **lib/config.py**: Added `_fanartbg_state` module-level dict to persist the selected image across service ticks without re-picking unless the weather condition or day/night state actually changes.
- **lib/weather.py**: `setother()` now sets `current.fanartbg` window property (a `special://` path to a specific image file) alongside the existing `current.fanartcode`. The skin reads this for the home screen background.
- **lib/service.py**: Added startup cache pre-load — on first service tick, `mode='update'` runs immediately from cached JSON before any network download. The background now appears within a second of Kodi start rather than waiting for the full download cycle to complete.

### Skin — Includes_Backgrounds.xml (companion change, not in this zip)

- **HomeFanart** include: inserted a permanent weather background layer (`current.fanartbg`) between the black base and the library fanart `multiimage`. When the library multiimage fades out (e.g. navigating to Settings or Add-ons which have no fanart), the background now falls through to the stable weather image instead of going black.

---

## [2.4.6] - 2026-04-21

### Fixed — 24 bugs fixed across 3 audit passes

**Pass 1 — Core crashes and shutdown hang**
- **lib/service.py**: Service loop lacked `abortRequested()` checks inside download and notification loops — Kodi had to force-kill the script after 5 seconds on every shutdown; abort guards added before each major phase and inside each locid loop
- **lib/service.py / monitor.py / config.py / api.py**: `settingrpc("weather.currentlocation")` can return `None` if the JSON-RPC call fails; `str(None)` = `'None'` caused `float('')` crashes downstream in `config.loc()`; guarded with `or 1` fallback at all four call sites
- **lib/weather.py**: Iemradar frame download loop (12 frames × 9 tiles) had no abort check; added break on `abortRequested()` so shutdown isn't blocked by tile fetching
- **lib/utils.py**: `setting()` — `int(value)` and `float(value)` were unguarded; empty or corrupt setting strings raised `ValueError`; now returns `0` / `0.0` as fallback
- **lib/utils.py**: `getprop()` — `if idx:` was falsy for `idx=0`; the `is_day` day/night lookup fell through to the scalar branch for the first hourly slot, producing night icons for current daytime conditions; changed to `if idx is not None:`
- **lib/api.py**: `getloc()` and `setloc()` — `json.loads(geturl(...))` raised `TypeError` when `geturl()` returned `None` on network failure; now checks the return before parsing
- **lib/api.py**: `getmap()` and `getdata()` — `url` variable was never initialised; an unrecognised map or data type would hit `geturl(url)` and raise `UnboundLocalError`; both functions now initialise `url = None` with a guarded early return
- **lib/api.py**: gctemp/gcwind code paths called `.format()` on `config.map_api.get()` result which is `None` for those keys; guarded with early return and log
- **lib/config.py**: `maxdays` — our `int()` fix changed `int('')` from raising `ValueError` to returning `0`; a corrupt `fcdays` setting would have given `maxdays=0` and broken the API URL; floors to 8 if value < 3
- **lib/config.py**: `loc.cid = str(settingrpc(...))` — if RPC returns `None`, `str(None)` = `'None'` (a literal string, not a location ID); guarded with `or 1` fallback
- **resources/settings.xml**: `loc2tz`, `loc3tz`, `loc4tz` hidden settings all had `RunScript(weather.kodiweather,loc1)` copy-pasted as their button action; corrected to `loc2`, `loc3`, `loc4`
- **resources/settings.xml**: Removed 69 lines of orphaned EU pollen alert groups (alder, birch, grass, mugwort, olive, ragweed, aqieu) — dead settings with no corresponding alert map entries after EU pollen was stripped

**Pass 2 — Index zero, graph crashes, notification issues**
- **lib/utils.py**: `notification()` — `int(setting('alert_duration'))` was raw Python `int()`, bypassing the guarded `setting(..., 'int')` fix; empty setting would raise `ValueError`
- **lib/utils.py**: `getprop()` graph unit — `idxnow` can be `None` when data is stale; `range(None, None+24)` raised `TypeError`; also `lv` can be empty if all 24 data reads fail, making `min([])` / `max([])` raise `ValueError`; both cases now return early
- **lib/weather.py**: `setalert()` — `if not idx:` treated index 0 as invalid; changed to `if idx is None:`
- **lib/weather.py**: `setmulti()` — same `if not idx:` → `if idx is None:` fix
- **lib/weather.py**: `setother()` — iemradar frame file list was not filtered for numeric stems; any stray non-numeric `.png` in the radar subfolder would crash `int(file.stem)` and blank all map properties; fixed with `f.stem.isdigit()` filter at collection time
- **lib/weather.py**: `notification()` — `waitForAbort(duration)` where `duration = utils.setting('alert_duration', 'int')`; our int() fix means an empty setting now returns `0` instead of raising; `waitForAbort(0)` is a no-op causing rapid-fire notifications; floored to `max(3, ...)` seconds

**Pass 3 — Silent failures and unhandled None**
- **lib/config.py**: `addon.alerthours = utils.setting('alert_hours', 'int', cache)` — same int() regression; `0` gives `range(idx, idx+0)` which silently disables all weather alerts; floored to `max(1, ...)`
- **lib/api.py**: `mapmerge()` OSM branch called `image.save()` with no error handling; disk-full or permission errors propagated and crashed the merge, leaving no base map tile; the radar branch already had `try/except`; now both are consistent
- **lib/conv.py**: `dp()` — `float(value)` was unconditional; API responses can contain `null` for some fields which Python reads as `None`; `float(None)` raised `TypeError` mid-graph, crashing the entire `lc` list comprehension and blanking the whole graph; wrapped in `try/except (TypeError, ValueError)` returning 0

---

## [2.4.3] - 2026-03-26

### Fixed
- **lib/api.py**: Directory cleanup on location change used `os.remove()` on all cache items; the `iemradar/` subdirectory raised `IsADirectoryError`; fixed with `is_file()` check and `shutil.rmtree()` for directories

## [2.4.2] - 2026-03-26

### Added
- **Fanart folder mapping** — Redirects clone condition codes to master folders, enabling resource.images.weatherfanart.echo to eliminate ~1.2GB of duplicate images
- **config.py**: `map_fanart` dict mapping 50 Yahoo weather codes to 17 master folders
- **config.py**: `get_fanart_folder()` helper function

### Changed
- All `fanartcode` property assignments now use `config.get_fanart_folder()` wrapper

## [2.4.1] - 2026-03-21

### Fixed
- **config.py**: NWS alerts 400 error — api.weather.gov no longer accepts `limit` parameter; removed `&limit=10` from noaalerts URL

## [2.4.0] - 2026-03

### Changed
- Radar provider migrated from RainViewer to IEM NEXRAD (mesonet.agron.iastate.edu)
- 12-frame animated radar with synthetic timestamps
- Radar frames stored in per-location `iemradar/` subdirectory
