# Echo Sports Changelog

All notable changes to plugin.video.echosports are documented here.

---

## [0.6.7] - 2026-03-31

### Added
- **Racing/Motorsport section** - New top-level menu item (lime colored)
- **PitSport integration** - Ported from Torque Live addon
  - Supports MotoGP, IndyCar, IndyNXT, F1, NASCAR, and more
  - Live Now and Schedule views
  - Next.js RSC payload parsing
  - pushembdz.store API probing for stream resolution
  - HLS playback with inputstream.adaptive support
- New files: `lib/sources/pitsport.py`, `lib/racing.py`, `lib/racing_handlers.py`
- Added `inputstream.adaptive` as optional dependency

### Technical
- Racing menu routes through dedicated `_route_racing()` handler
- PitSport scraper handles complex Next.js server-rendered content
- Fallback to native Kodi player if inputstream.adaptive unavailable

---

## [0.6.6] - 2026-03-31

### Fixed
- **ResolveURL Settings menu item** now works properly
- Settings items no longer marked as `IsPlayable='true'` (was causing Kodi errors)
- Added dedicated `_add_settings_item()` method for non-playable menu items

### Added
- ResolveURL Settings added to main menu (yellow highlighted)
- Debug logging for ResolveURL settings action

---

## [0.6.5] - 2026-03-31

### Fixed
- **Dead link detection now actually works**
- Bug: Creating new resolver instance in error handler lost `_last_error` state
- Fix: Keep same resolver instance throughout play function
- Added debug logging: "last_error=dead_link" visible in log on failure

---

## [0.6.4] - 2026-03-31

### Added
- ResolveURL settings button in addon settings
- Dead link detection with specific error dialogs
- Debrid status check before playback attempts

### Fixed
- Settings.xml uses v1 format with `Addon.OpenSettings()` builtin

---

## [0.6.3] - 2026-03-31

### Added
- ResolveURL settings integration
- Better error messages for debrid failures
- Auth error detection for re-authorization prompts

---

## [0.6.2] - 2026-03-31

### Fixed
- **NFL parsing fixed** - "0 dir blocks" on Windows
- Root cause: urllib with manual decode behaved differently than requests
- Fix: Switched `nfl_source.py` to use `requests.Session()` like `fod_comprehensive.py`
- Simplified regex flags from `re.DOTALL | re.IGNORECASE` to just `re.S`

### Changed
- NFL 23/24 season URL paths corrected

---

## [0.6.1] - 2026-03-31

### Changed
- NFL moved under dedicated NFL menu (was scattered)
- Added debug logging throughout NFL module

---

## [0.6.0] - 2026-03-30

### Added
- **NFL Replays integration** via NFL Rewind XML feeds
- 3 seasons of content: 25/26, 24/25, 23/24
- All regular season weeks + playoffs (Super Bowl, Pro Bowl, Conference, Divisional, Wildcard)
- Magnet links route through Real-Debrid

### Technical
- New files: `lib/sources/nfl_source.py`, `lib/nfl.py`, `lib/nfl_handlers.py`
- XML feed parsing with requests library

---

## [0.5.2] - 2026-03-30

### Fixed
- **CRITICAL: Magnet detection bug**
- Bug: Magnets with `.mp4`/`.mkv` in display name (`dn=` parameter) falsely detected as direct streams
- Fix: Check `magnet:` prefix BEFORE checking file extensions
- Pattern applied in both `fod.py` and `nfl.py`:
  ```python
  is_magnet = url.startswith('magnet:')   # Check FIRST
  is_direct = False
  if not is_magnet and not is_mega:
      is_direct = url.endswith('.mp4')    # Only then check extension
  ```

---

## [0.5.1] - 2026-03-30

### Fixed
- FOD playback issues resolved
- Improved stream detection logic

---

## [0.5.0] - 2026-03-30

### Added
- **FOD (Fights on Demand) integration**
- Boxing and MMA content via XML feeds
- Debrid support (magnets, Mega.nz)
- Free sections via luluvdo hosters

### Technical
- New files: `lib/sources/fod_comprehensive.py`, `lib/fod.py`, `lib/fod_handlers.py`
- Feed base: `https://mylostsoulspace.co.uk/FightsOnDemand/`

---

## [0.4.1] - 2026-03-30

### Fixed
- Settings.xml labels corrected

---

## [0.4.0] - 2026-03-30

### Added
- **ResolveURL integration** for debrid and hoster support
- Support for Real-Debrid, Premiumize, AllDebrid
- New file: `lib/resolvers/resolveurl_resolver.py`

---

## [0.3.0] - 2026-03-30

### Added
- **Wrestling section** with 1700+ items
- Live 24/7 streams (direct CDN)
- WWE, AEW, TNA, indie promotions
- PPV archives, WrestleMania collection

### Technical
- New files: `lib/sources/wrestling_comprehensive.py`, `lib/wrestling.py`, `lib/wrestling_handlers.py`
- Feed base: `https://l3grthu.com/hades/wod21/`

---

## [0.2.0] - 2026-03-29

### Added
- **wilderness.click decoder CRACKED**
- Custom base64 chunk reorder algorithm implemented
- LeagueDo embed streams now playable

### Technical
- Algorithm in `lib/resolvers/embed.py`:
  1. Base64 decode payload
  2. Split into 4 chunks
  3. Remove char[3] from each
  4. Reorder [2,0,3,1]
  5. Base64 decode each chunk
  6. Join and base64 decode final result
  7. Parse JSON for stream_url

---

## [0.1.0] - 2026-03-29

### Initial Release
- Basic addon structure
- LeagueDo source (super.league.do scraper)
- Sportsfire source (schedule only, streams encrypted)
- Direct stream resolver
- Menu system with sport categories

---

## Version Summary

| Version | Date | Highlights |
|---------|------|------------|
| 0.6.7 | 2026-03-31 | Racing/Motorsport (PitSport) |
| 0.6.6 | 2026-03-31 | ResolveURL settings button fix |
| 0.6.5 | 2026-03-31 | Dead link detection fix |
| 0.6.4 | 2026-03-31 | Debrid status, error dialogs |
| 0.6.2 | 2026-03-31 | NFL parsing fix (Windows) |
| 0.6.0 | 2026-03-30 | NFL Replays |
| 0.5.2 | 2026-03-30 | Magnet detection fix |
| 0.5.0 | 2026-03-30 | FOD Boxing/MMA |
| 0.4.0 | 2026-03-30 | ResolveURL integration |
| 0.3.0 | 2026-03-30 | Wrestling section |
| 0.2.0 | 2026-03-29 | wilderness.click cracked |
| 0.1.0 | 2026-03-29 | Initial release |
