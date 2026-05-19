# Changelog

All notable changes to weather.kodiweather.

## [2.4.13] - 2026-05-19

### Fixed — Heavy rain/drizzle showing snow/sleet icon

- **lib/config.py** (`map_wmo`): WMO codes 55, 65, and 82 were all mapped to Kodi weather code 18 (Sleet), which `map_fanart` then redirects to fanart folder 5 (Mixed Rain and Snow). All three are pure rain/drizzle conditions with no ice involved:
  - `55` = Dense drizzle → was 18 (Sleet), now **12** (Heavy Showers)
  - `65` = Heavy rain → was 18 (Sleet), now **12** (Heavy Showers)
  - `82` = Heavy rain showers → was 18 (Sleet), now **12** (Heavy Showers)

## [2.4.12] - 2026-05-19

### Fixed — Bug sweep #2: forecast condition, alerts, unit precision

- **lib/utils.py**: Daily forecast cards (`DayX.Condition`) showed the statistical *mode* (most common WMO code) of the personalized forecast window instead of the worst condition of the full day. If heavy rain occurred only at 6am and the rest of the day was cloudy, the card showed "Cloudy". Root cause: the `timeofday` block computed `mode(sorted(l))` after slicing with `fcstart`/`fcend`, then overwrote the `day{n}.*` properties that Open-Meteo's daily summary had already set correctly. Fix: capture `l_full` before slicing; use `max(l_full)` for `day{n}.condition/outlook/outlookicon/fanartcode` (the Kodi standard daily card properties). Personalized `daily.{n}.*` properties still use the mode of the active window. `maxoutlook` now compares full-day worst vs personalized-window typical.

- **lib/service.py**: Alert notifications fired for every configured location simultaneously (all default to `loc{n}alert=true`), not just the currently selected one. Root cause: the msgqueue loop in service.py queued alerts from all locations into the shared `config.addon.msgqueue`, then sent all of them. Fix: queue alerts only for `current` (the Kodi-selected location). The `loc{n}alert` setting now controls whether alerts fire *when that location is selected*.

- **lib/conv.py**: Distance conversion used `/ 1609` instead of `/ 1609.344` — 0.02% error per mile.

- **lib/conv.py**: Precipitation mm→inches used `* 0.039` instead of `* 0.0393701` — 0.8% error (25.4mm would display as 0.99in instead of 1.00in).

- **lib/conv.py**: `moonphase()` and `moonphaseimage()` did not handle `deg=360` (equivalent to new moon / 0°). Met.no can return exactly 360 at the new moon. Both functions now normalize with `% 360` before the range checks so 360 maps cleanly to the new-moon branch.

- **lib/api.py**: `mapmerge()` created the tile composite at `(756, 756)` — 12px short of the correct `(768, 768)`. Three tiles × 256px = 768px per axis; the 756 size clipped 12px from the right and bottom edges of the rightmost/bottommost tiles in every OSM and radar composite.

## [2.4.11] - 2026-05-13

### Fixed — Root cause of resources/34/ folder error (and all equivalent redirected codes)

**Root cause confirmed from Kodi debug.log:** `XFILE::CDirectory::GetDirectory - Error getting ...resources/34/`. Folder 34 does not exist in the fanart pack (consolidated into 32 via `map_fanart`). The folder `34` was being requested because the skin's home screen builds its fanart background path from `current.outlookicon` — stripping the `.png` extension to get the folder number — rather than from `current.fanartcode`. The `fanartcode` property correctly went through `get_fanart_folder` (34→32); the `outlookicon` property did not, leaving a raw unreduced code that the skin used as a directory name.

- **lib/utils.py** (`unit == 'image'`, non-day branch): `current.outlookicon`, `hourly.X.outlookicon`. Previously set to bare `{raw_kodi_code}.png` (e.g. `34.png`). Now routes through `get_fanart_folder` so the emitted value matches the existing fanart folder (e.g. `32.png`). The `resource.images.weathericons.default` pack contains icons for both 32 and 34, so the redirected number is still a valid icon for that pack.
- **lib/utils.py** (TimeOfDay block — 9 inline setters): `daily.X.overview.outlookicon`, `daily.X.outlookicon`, `day{N}.outlookicon`, `timeofday.X.outlookicon`, `daily.X.{tod}.outlookicon`, and all corresponding `maxoutlookicon` variants. All now use `safe_fanart_code() or map_wmo.get()` so any property potentially used as a directory name carries only a folder that exists in the pack.

### Notes

- `day{N}.outlookicon` (the `day`-target, full `resource://resource.images.weathericons.default/...` URI) is intentionally left using the raw Kodi code in `unit == 'image'`'s day-branch: it carries a full absolute path, not a bare number, so the skin engine never interprets it as a fanart folder name.
- The only `map_wmo` reference now remaining in the property-setting layer outside of the `code` and `image` unit handlers is the `day`-target URI on line 275. All bare-number outputs that could be interpreted as folder names are redirected through `safe_fanart_code`.
## [2.4.10] - 2026-05-13

### Fixed — Fanart folder redirect None-propagation

- **lib/config.py**: `get_fanart_folder()` had no guard for `None` input. If `map_wmo.get(...)` returned `None` for an unknown WMO code, the value propagated through `map_fanart.get(None, None)` = `None`, then `str(None)` = `'None'`, and Kodi set the `fanartcode` window property to the string `'None'`. The skin then tried to open `resources/None/`, logging errors. Added early `if code is None: return None`.
- **lib/config.py**: Added `safe_fanart_code(wmo_code, isday)` helper that encapsulates both `map_wmo` and `map_fanart` lookups with explicit None guards. Returns `None` on any miss (caller uses `or ''`). Replaces five scattered inline `config.get_fanart_folder(config.map_wmo.get(...))` one-liners throughout `utils.py`.
- **lib/utils.py**: All five inline `get_fanart_folder(map_wmo.get(...))` calls in the TimeOfDay and daily-per-segment blocks migrated to `safe_fanart_code(...) or ''`.
- **lib/utils.py** (`unit == 'code'` in `getprop()`): Same None-propagation fixed. Now raises `TypeError` with a diagnostic message at each missing step so `setmap`'s existing handler sets the property to `''` instead of `'None'`.

### Fixed — `maxoutlookicon` showed wrong icon

- **lib/utils.py** (lines 651, 655): `daily.X.overview.maxoutlookicon` and `daily.X.maxoutlookicon` were built with `code` (modal condition) instead of `mcode` (most severe condition). The property is only written when `mcode > code`, so the displayed icon was always wrong in that branch.
## [2.4.9] - 2026-05-07

### Fixed — Black weather background race conditions

Long-standing intermittent issue where `current.fanartbg` would briefly go empty and the home-screen weather background would render as a black tile. Three independent failure paths fed into the same end state and none of them recovered:

- **lib/api.py**: `getdata()` and `getnoaalerts()` wrote JSON files in place. A concurrent reader landing inside the write window saw a truncated file, `json.load` raised, `getfile()` returned None, `setdata()` returned early at line 138 *before setting `current.fanartcode`*, and `setother()` then wrote `current.fanartbg=''`. Now writes to `<file>.tmp` and uses `os.replace()` to atomically swap, so readers always see either the old complete file or the new complete file. Atomic on both POSIX and Windows.
- **lib/weather.py**: `setother()` actively wiped a known-good `current.fanartbg` with `''` whenever `current.fanartcode` was briefly missing — which is exactly what happens during the partial-write race above and during Open-Meteo `weather_code: null` hiccups. Now always calls `get_fanartbg()` and lets the function's own fallback chain decide what to write.
- **lib/config.py**: `get_fanartbg()` returned `''` whenever the per-code folder lookup failed, even though the resource pack ships `Fallback_00.jpg` through `Fallback_03.jpg` in the `resources/` root specifically as last-resort backgrounds. Rewrote with a three-level fallback chain: real per-code image (cached, stable) → previously-cached real image when `code` is empty (preserves the last good background through brief data outages) → random `Fallback_*.jpg` (cached separately with a `fallback` flag so the next service tick re-tries the real folder and recovers automatically) → `''` only if the resource pack itself is unreadable. Added debug-level logging at each step so future failures are traceable in the Kodi log.

### Fixed — Audit pass

- **lib/config.py**: `maxdays` was set once at module import and never refreshed. Changing the `fcdays` setting in the addon UI had no effect on the API URL (`api.py:85`), the TimeOfDay loop (`utils.py:570`), or the four `setmulti` calls in `weather.py` until Kodi restarted the Python process. Refresh now happens inside `addon()` so `config.init()` (called from `monitor.onSettingsChanged`) picks up the new value on the next service tick. Module-level fallback retained for the brief import → first-`init()` window.
- **lib/utils.py**: `notification()` computed `(setting('alert_duration', 'int') - 2) * 1000`. The 2.4.6 guard that makes `setting(..., 'int')` return `0` on a corrupt value meant a corrupted settings.xml could pass `-2000` to `xbmcgui.Dialog().notification`. Floored at `max(3, ...)` seconds before the multiply, matching the same floor that 2.4.6 added in `weather.py:notification`.
- **lib/utils.py**: `getprop()` had no fallthrough for `len(map[1]) > 3`. Any future 4-element key path would leave `content` unbound and raise `UnboundLocalError` two lines later. Added an explicit `raise TypeError` with the offending path so `setmap`'s existing `TypeError` handler logs cleanly instead of crashing the update.
- **lib/conv.py**: `direction()` returned `None` for non-integer inputs because all 16 sectors used integer-only ranges (e.g. `>= 12 and <= 33`); a value of `11.5` matched no branch. Added an `int(round(float(deg)))` coercion at entry with a guard for non-numeric input.
- **lib/conv.py**: `moonphase()` and `moonphaseimage()` had the same float-input gap from their discrete-equality boundary checks (`358..2`, `88..92`, etc.). Same `int(round(float(deg)))` coercion at entry.
- **lib/conv.py**: `season()` used closed intervals on both ends, so day 172 (summer solstice) returned spring, day 264 (autumn equinox) returned summer, and day 355 (winter solstice) returned autumn. Switched to half-open intervals so each solstice/equinox starts the new season.
- **MyWeather.xml**: bundled copy was older than the deployed version. Replaced with the corrected deployed XML, which contains: condition label `<height>` 40 → 80 (font30 descender clipping on conditions like "Mostly Sunny"), following label `<top>` 255 → 295 to clear the taller condition label, `36Hour.IsFetched` → `Weekend.IsFetched` copy-paste fix, `Daily.IsFetched` → `Hourly.IsFetched` copy-paste fix, and removal of four duplicated `$INFO[ListItem.Label]` overlay controls.

### Notes — observed but not changed in this pass

- The skin reads `36Hour.IsFetched`, `Weekend.IsFetched`, `36Hour.X.*`, and `Weekend.X.*`, none of which the addon writes. The addon's `addprop(f'{prop}.isfetched', 'true')` covers `current`, `weather`, `hourly`, `daily`, `timeofday`, `map` only. The `36Hour` / `Weekend` bridge must live in one of the skin's other Includes files (likely `Includes_Home.xml`, `Includes_LiveBG.xml`, or `Includes_Backgrounds.xml`); confirmed not in `Includes.xml` or in `MyWeather.xml`.
- `addon.maxlocs` is named like a count but used as the exclusive upper bound of `range(1, maxlocs)`. Code is consistent and works correctly; left alone to avoid touching every call site.
- Several files had a top-level `import os` that was never used (`lib/service.py`, `lib/utils.py`, `lib/config.py`). `lib/api.py`'s `import os` is now actually used by the atomic-write path. The other three left alone — cosmetic.
- `lib/utils.py:362` uses `round(conv.speed(...), True)` then `int(...)`, which double-rounds. Cosmetic; left alone.

---

## [2.4.8] - 2026-05-03

### Fixed — Weather fanart background black screen

- **lib/config.py**: `get_fanartbg()` was building `special://home/addons/resource.images.weatherfanart.echo/{code}/` (addon root). Images live under `resources/{code}/`. Added `resources/` to the path. Affected every condition code — `current.fanartbg` returned `''` and the background was always black.

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
