# Echo Sports Kodi Addon - Complete Handoff Document

**Version:** 0.6.7  
**Last Updated:** March 31, 2026  
**Developer:** Echo-Storm  
**GitHub:** https://github.com/Echo-Storm  

---

## Quick Start

```bash
# Install
1. Copy plugin.video.echosports-0.6.7.zip to Kodi device
2. Kodi → Add-ons → Install from zip file → Select zip
3. (Optional) Install ResolveURL for debrid support
4. (Optional) Configure Real-Debrid in ResolveURL Settings

# Dependencies (auto-installed or optional)
- script.module.requests (required)
- script.module.six (required)  
- script.module.resolveurl (optional - for debrid)
- inputstream.adaptive (optional - better HLS)
```

---

## Current Addon Structure

```
plugin.video.echosports/
├── addon.xml                          # v0.6.7, metadata and dependencies
├── main.py                            # Entry point
├── CHANGELOG.md                       # Version history
├── HANDOFF.md                         # This document
├── lib/
│   ├── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── router.py                  # Main URL router, menu builder
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract source class
│   │   ├── leaguedo.py                # LeagueDo/super.league.do scraper ✅
│   │   ├── sportsfire.py              # Sportsfire API (schedule only) ❌
│   │   ├── pitsport.py                # PitSport motorsport scraper ✅ NEW
│   │   ├── wrestling_comprehensive.py # Wrestling XML feeds ✅
│   │   ├── fod_comprehensive.py       # FOD XML feeds ✅
│   │   └── nfl_source.py              # NFL Rewind XML feeds ✅
│   ├── resolvers/
│   │   ├── __init__.py
│   │   ├── direct.py                  # Direct URL passthrough
│   │   ├── embed.py                   # Embed + wilderness.click decoder ✅
│   │   ├── ytdlp.py                   # System yt-dlp + ResolveURL fallback
│   │   └── resolveurl_resolver.py     # ResolveURL wrapper ✅
│   ├── schedule/
│   │   ├── __init__.py
│   │   └── cache.py                   # Event caching system
│   ├── wrestling.py                   # Wrestling action router
│   ├── wrestling_handlers.py          # Wrestling UI handlers
│   ├── fod.py                         # FOD action router
│   ├── fod_handlers.py                # FOD UI handlers
│   ├── nfl.py                         # NFL action router
│   ├── nfl_handlers.py                # NFL UI handlers
│   ├── racing.py                      # Racing action router ✅ NEW
│   └── racing_handlers.py             # Racing UI handlers ✅ NEW
└── resources/
    ├── icon.png
    ├── fanart.jpg
    ├── settings.xml                   # Addon settings (v1 format)
    ├── language/resource.language.en_gb/strings.po
    └── media/wrestling/icon.png + fanart.jpg
```

---

## Menu Structure

```
Main Menu:
├── Live Events (LeagueDo - all sports)
├── NFL →
│   ├── Live NFL (LeagueDo)
│   └── NFL Replays →
│       ├── 25/26 Season (23 items)
│       ├── 24/25 Season (27 items)
│       └── 23/24 Season (23 items, some broken)
├── NBA (LeagueDo)
├── NHL (LeagueDo)
├── MLB (LeagueDo)
├── Golf (LeagueDo)
├── [COLOR lime]Racing/Motorsport[/COLOR] → NEW in 0.6.7
│   ├── Live Now (PitSport)
│   └── Schedule (PitSport)
├── Boxing/MMA (FOD) →
│   ├── Latest UFC/MMA Events
│   ├── UFC PPV Replays (debrid)
│   ├── UFC Fight Night (debrid)
│   ├── Free UFC (luluvdo hosters)
│   ├── Boxing Replays (debrid)
│   └── Free Boxing
├── Wrestling (WOD) →
│   ├── Live 24/7 Streams (direct CDN)
│   ├── WWE Raw/Smackdown/NXT
│   ├── WrestleMania Archives
│   ├── PPV Events
│   ├── AEW Content
│   ├── TNA/Impact
│   └── Indie Wrestling
├── [COLOR yellow]ResolveURL Settings[/COLOR]
└── Settings
```

---

## Feature Status

### ✅ WORKING

| Feature | Source | Notes |
|---------|--------|-------|
| LeagueDo live sports | super.league.do | Full chain with wilderness.click decode |
| wilderness.click decode | Custom algorithm | Base64 chunk reorder (see embed.py) |
| Wrestling Live 24/7 | l3grthu.com | Direct CDN streams, no auth |
| Wrestling VOD | mail.ru, dood | Needs ResolveURL or yt-dlp |
| FOD Boxing/MMA (debrid) | mylostsoulspace.co.uk | Magnets/Mega via Real-Debrid |
| FOD Free sections | luluvdo hosters | Needs ResolveURL or yt-dlp |
| NFL Replays (debrid) | mylostsoulspace.co.uk | Magnets via Real-Debrid |
| Racing/Motorsport | pitsport.xyz | MotoGP, IndyCar, F1, etc. |
| ResolveURL integration | script.module.resolveurl | RD/PM/AD support |
| Dead link detection | ResolveURL errors | Shows specific error dialog |
| Settings button | executebuiltin | Opens ResolveURL settings |

### ⚠️ PARTIAL / NEEDS WORK

| Feature | Issue | Workaround |
|---------|-------|------------|
| NFL 23/24 season | Some feeds point to dead URLs | Skip broken entries |
| Some Mega.nz links | Uploader deleted files (404) | Try alternate links |
| Wrestling VOD hosters | Need ResolveURL configured | Install + auth RD |
| PitSport streams | May need inputstream.adaptive | Falls back to native |

### ❌ NOT WORKING / BLOCKED

| Feature | Blocker | Notes |
|---------|---------|-------|
| Sportsfire streams | Native DES decryption | Schedule works, streams encrypted |
| Streamfire API | Returns success:0 | May be down |

---

## Source Details

### 1. LeagueDo (super.league.do)
**Status:** ✅ WORKING  
**File:** `lib/sources/leaguedo.py`

Scrapes live sports events from super.league.do. Uses wilderness.click for stream embedding.

**wilderness.click Algorithm (CRACKED):**
```python
# Input: http_stream from embed page
# 1. Base64 decode the main payload
# 2. Split into 4 equal chunks
# 3. Remove character at index 3 from each chunk
# 4. Reorder chunks: [2, 0, 3, 1]
# 5. Base64 decode each chunk
# 6. Join all decoded chunks
# 7. Base64 decode the final result
# 8. Parse JSON to get stream_url
```
See `lib/resolvers/embed.py` → `_resolve_wilderness_html()`

### 2. PitSport (pitsport.xyz)
**Status:** ✅ WORKING (NEW in 0.6.7)  
**File:** `lib/sources/pitsport.py`

Motorsport streaming site. Ported from Torque Live addon.

**Features:**
- MotoGP, IndyCar, IndyNXT, F1, NASCAR, etc.
- Live Now + Schedule views
- Next.js RSC payload parsing
- pushembdz.store API probing
- HLS stream resolution

### 3. Wrestling (WOD - l3grthu.com)
**Status:** ✅ WORKING  
**File:** `lib/sources/wrestling_comprehensive.py`

XML-based feeds with 1700+ items across WWE, AEW, TNA, indie promotions.

**Feed Base:** `https://l3grthu.com/hades/wod21/`
**Key Feeds:**
- `/live.xml` - 24/7 streams
- `/latestshows/raw.xml`, `/smackdown.xml`, `/nxtmain.xml`
- `/wrestlemania/mainwm.xml`, `/ppv/ppvmain.xml`
- `/aew/aewppv.xml`, `/tna/tnamain.xml`

### 4. FOD (Fights on Demand)
**Status:** ✅ WORKING  
**File:** `lib/sources/fod_comprehensive.py`

Boxing and MMA content via XML feeds.

**Feed Base:** `https://mylostsoulspace.co.uk/FightsOnDemand/`
**Key Feeds:**
- `/fodmain-new.xml` - Main menu
- `/latestufc-mmaevents.xml` - Latest UFC (2026)
- `/ufcevents/ufcppv-new.xml` - UFC PPV (debrid)
- `/boxing/boxingreplays-new.xml` - Boxing (debrid)
- `/nondebridufc.xml` - Free UFC (hosters)

### 5. NFL Rewind
**Status:** ✅ WORKING  
**File:** `lib/sources/nfl_source.py`

NFL replay content via XML feeds.

**Feed Base:** `https://mylostsoulspace.co.uk/NFLRewind/`
**Key Feeds:**
- `/xmls/MainXml/nflrewind-main.xml` - Season list
- `/xmls/25-26/nflreplaysmain25.xml` - Current season
- `/xmls/25-26/nflreplays{1-18}-25.xml` - Regular season weeks
- `/xmls/25-26/nflreplayswildcard-25.xml` - Playoffs

### 6. Sportsfire (BLOCKED)
**Status:** ❌ Streams encrypted  
**File:** `lib/sources/sportsfire.py`

Schedule API works, but `http_stream` values are DES-encrypted by native library.

**API:** `POST https://spfire.work/tv/index.php?case=get_schedule_by_type`
**Token:** `9120163167c05aed85f30bf88495bd89`
**Key:** `ww23qq8811hh22aa` (found but not working)

See `SPORTSFIRE_NOTES.md` for full reverse engineering details.

---

## Resolution Chain

### Magnet/Mega Links (FOD, NFL)
```
1. Check magnet: prefix FIRST (order matters!)
2. Check mega.nz domain
3. Route to ResolveURL → Real-Debrid/Premiumize/AllDebrid
4. Get direct HTTPS link from debrid service
5. Play via Kodi
```

### Direct Streams
```
1. Check .m3u8/.mp4/.mkv extension (only if NOT magnet/mega)
2. Play directly via Kodi
3. Use inputstream.adaptive for HLS if available
```

### File Hosters (luluvdo, dood, etc.)
```
1. Try ResolveURL
2. Fallback to system yt-dlp if available
3. Show error if both fail
```

### LeagueDo Embeds
```
1. Fetch event page from super.league.do
2. Extract channel links
3. Fetch embed page
4. Detect wilderness.click or other embed type
5. Apply appropriate decoder
6. Play resolved stream
```

---

## Error Handling

### Dead Link Detection
The resolver tracks `_last_error` state:
- `'dead_link'` - 404 in error → "Link Dead / Removed" dialog
- `'auth_error'` - token/auth issue → re-auth message
- `'unknown'` - generic failure → standard error

**Important:** Keep the SAME resolver instance throughout the play function to preserve error state.

### Debrid Status Check
```python
resolver.check_debrid_status()
# Returns: {
#   'available': True,
#   'real_debrid': True,
#   'premiumize': False,
#   'all_debrid': False,
#   'error': None
# }
```

---

## Settings

### settings.xml (v1 format)
```xml
<settings>
    <category label="Playback">
        <setting id="use_resolveurl" type="bool" label="Use ResolveURL" default="true"/>
        <setting id="open_resolveurl_settings" type="action" 
                 label="Open ResolveURL Settings" 
                 action="Addon.OpenSettings(script.module.resolveurl)"/>
    </category>
    <category label="Advanced">
        <setting id="debug_logging" type="bool" label="Debug Logging" default="false"/>
    </category>
</settings>
```

---

## Dependencies

### Required
- `xbmc.python` 3.0.0+
- `script.module.requests` 2.22.0+
- `script.module.six` 1.15.0+

### Optional
- `script.module.resolveurl` 5.1.0+ (for debrid support)
- `inputstream.adaptive` 21.0.0+ (for better HLS)

### System (not Kodi addons)
- `yt-dlp` in PATH (fallback resolver)

---

## Key Bug Fixes History

### v0.5.2 - Magnet Detection
**Bug:** Magnets with `.mp4`/`.mkv` in display name falsely detected as direct streams.
**Fix:** Check `magnet:` prefix BEFORE checking file extensions.

### v0.6.2 - NFL Parsing
**Bug:** "0 dir blocks" on Windows when parsing NFL feeds.
**Fix:** Switch from urllib to requests library (consistent behavior).

### v0.6.5 - Dead Link Detection
**Bug:** Creating new resolver instance in error handler lost `_last_error` state.
**Fix:** Keep same resolver instance throughout play function.

### v0.6.6 - Settings Button
**Bug:** `IsPlayable='true'` on settings items caused Kodi errors.
**Fix:** Use separate `_add_settings_item()` without IsPlayable property.

---

## Files for Reference

### Extracted APKs
```
/home/claude/sportsfire_arm7/                    # Sportsfire APK
/home/claude/sportsfire_arm7/lib/armeabi-v7a/libcompression.so  # Native crypto
/home/claude/sportsfire_arm7/decompiled/         # JADX output
```

### Reference Addons
```
/home/claude/fod_extract/plugin.video.fod/       # FOD addon
/home/claude/nflrewind_extract/plugin.video.nflrewind/  # NFL Rewind
/home/claude/torque_ref/plugin.video.torquelite/ # Torque Lite (JetExtractors)
/home/claude/torque_ref/plugin.video.torquelive/ # Torque Live (PitSport)
```

### Tools
```
/tmp/jadx/bin/jadx                               # Java decompiler
```

---

## Future Work / TODO

### High Priority
- [ ] Sportsfire stream decryption (see SPORTSFIRE_NOTES.md)
- [ ] Test racing streams with live events
- [ ] Verify ResolveURL settings button works

### Medium Priority
- [ ] Add JetExtractors support (from Torque Lite) for more sources
- [ ] Wrestling VOD hosted stream improvements
- [ ] Better error messages for specific hoster failures

### Low Priority / Nice to Have
- [ ] Event caching improvements
- [ ] Search functionality
- [ ] Favorites system
- [ ] EPG integration

### Blocked / Needs Research
- [ ] Sportsfire native lib RE (Ghidra/Frida)
- [ ] Find unmodified Sportsfire APK
- [ ] Traffic capture with mitmproxy

---

## Privacy / Legal Notes

- All magnet/Mega links route through debrid services (RD/PM/AD)
- ISP only sees HTTPS traffic to debrid provider
- No direct torrent connections from user's IP
- Addon is for personal use only
- Distributed privately via Echo-Storm handle

---

## Session Commands

```bash
# Package addon
cd /home/claude
zip -r plugin.video.echosports-X.Y.Z.zip plugin.video.echosports \
  -x "*.pyc" -x "*__pycache__*" -x "*.git*"

# View Kodi log (Windows)
type "%APPDATA%\Kodi\kodi.log" | find "[Echo Sports]"

# Test API
curl -X POST "https://spfire.work/tv/index.php?case=get_schedule_by_type" \
  -H "app-token: 9120163167c05aed85f30bf88495bd89" \
  -H "User-Agent: USER-AGENT-tvtap-APP-V2" \
  -d "type=0"

# Decompile APK
/tmp/jadx/bin/jadx -d output_dir --no-res classes.dex
```

---

## Contact / Distribution

- **GitHub:** https://github.com/Echo-Storm
- **Nexus Mods:** https://www.nexusmods.com/profile/Echo-Storm
- **Distribution:** Private, small group only
