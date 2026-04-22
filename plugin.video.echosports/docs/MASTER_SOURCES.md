# plugin.video.echosports - Master Source Intel

**Last Updated:** March 31, 2026  
**Current Version:** 0.6.7

---

## IMPLEMENTED SOURCES (ACTIVE)

### 1. LeagueDo / super.league.do ✅ WORKING
- **URL:** `https://super.league.do`
- **Method:** Web scrape - extract `window.matches` JSON from page
- **Pattern:**
  ```python
  new_pattern = r'window\.matches\s*=\s*JSON\.parse\(`(\[.+?\])`\)'
  ```
- **Event Structure:**
  ```json
  {
    "team1": "Team A",
    "team2": "Team B", 
    "team1Img": "icon_url",
    "sport": "Basketball",
    "league": "NBA",
    "startTimestamp": 1234567890000,
    "duration": 120,
    "channels": [
      {"name": "ESPN", "language": "EN", "links": ["stream_url1", "stream_url2"]}
    ]
  }
  ```
- **Status:** Fully working with wilderness.click decoder
- **File:** `lib/sources/leaguedo.py`
- **Resolver:** `lib/resolvers/embed.py` (wilderness.click algorithm)

### 2. PitSport (Motorsport) ✅ WORKING - NEW in 0.6.7
- **URL:** `https://pitsport.xyz`
- **Method:** Next.js RSC payload parsing + pushembdz API probing
- **Content:** MotoGP, IndyCar, IndyNXT, F1, NASCAR, etc.
- **Categories:** Live Now, Schedule
- **Status:** Fully working (ported from Torque Live addon by Dudelove00)
- **File:** `lib/sources/pitsport.py`
- **Technical Notes:**
  - Parses `self.__next_f.push()` payloads
  - Probes `/api/source/`, `/api/stream/`, `/api/video/` endpoints
  - Uses inputstream.adaptive for HLS when available

### 3. Wrestling (WOD) ✅ WORKING
- **Base URL:** `https://l3grthu.com/hades/wod21/`
- **Method:** XML feed parsing
- **Content:** 1700+ items across categories
- **Key Feeds:**
  ```
  /live.xml                      # 24/7 streams
  /latestshows/raw.xml           # WWE Raw
  /latestshows/smackdown.xml     # WWE Smackdown
  /latestshows/nxtmain.xml       # NXT
  /wrestlemania/mainwm.xml       # WrestleMania archives
  /ppv/ppvmain.xml               # PPV events
  /aew/aewppv.xml                # AEW content
  /tna/tnamain.xml               # TNA/Impact
  /indy.xml                      # Indie wrestling
  /mov.xml                       # Wrestling movies
  ```
- **Stream Types:** Direct CDN (live), mail.ru, dood (VOD)
- **Status:** Fully working
- **File:** `lib/sources/wrestling_comprehensive.py`

### 4. FOD (Fights on Demand) ✅ WORKING
- **Base URL:** `https://mylostsoulspace.co.uk/FightsOnDemand/`
- **Method:** XML feed parsing
- **Content:** Boxing, UFC, MMA
- **Key Feeds:**
  ```
  /fodmain-new.xml                       # Main menu
  /latestufc-mmaevents.xml              # Latest UFC (2026)
  /ufcevents/ufceventreplaysmain-new.xml # UFC events menu
  /ufcevents/ufcppv-new.xml             # UFC PPV (debrid)
  /ufcevents/ufcfightnightreplays-new.xml # UFC Fight Night
  /nondebridufc.xml                     # Free UFC (luluvdo)
  /nondebridmmareplays.xml              # Free MMA
  /boxing/boxingreplays-new.xml         # Boxing (debrid)
  /boxing/boxingreplays-nondebrid.xml   # Free boxing
  ```
- **Stream Types:** Magnets, Mega.nz (debrid), luluvdo (hosters)
- **Status:** Fully working with Real-Debrid
- **File:** `lib/sources/fod_comprehensive.py`

### 5. NFL Rewind ✅ WORKING
- **Base URL:** `https://mylostsoulspace.co.uk/NFLRewind/`
- **Method:** XML feed parsing
- **Content:** NFL replays (3 seasons)
- **Key Feeds:**
  ```
  /xmls/MainXml/nflrewind-main.xml      # Season list
  /xmls/25-26/nflreplaysmain25.xml      # 25/26 season (23 items)
  /xmls/24-25/nflreplaysmain24.xml      # 24/25 season (27 items)
  /xmls/23-24/nflreplaysmain23.xml      # 23/24 season (some broken)
  /xmls/25-26/nflreplaysprobowl-25.xml  # Pro Bowl
  /xmls/25-26/nflreplayssuperbowl-25.xml # Super Bowl
  /xmls/25-26/nflreplaysconference-25.xml # Conference
  /xmls/25-26/nflreplaysdivisional-25.xml # Divisional
  /xmls/25-26/nflreplayswildcard-25.xml # Wildcard
  /xmls/25-26/nflreplays{1-18}-25.xml   # Regular season weeks
  ```
- **Stream Types:** Magnets, Mega.nz (debrid required)
- **Known Issues:** Some 23/24 entries point to dead old URL structure
- **Status:** Fully working with Real-Debrid
- **File:** `lib/sources/nfl_source.py`

---

## BLOCKED SOURCES (NEED REVERSE ENGINEERING)

### 6. Sportsfire ❌ BLOCKED - Streams Encrypted
- **API Base:** `https://spfire.work/tv/index.php?case=`
- **Token:** `9120163167c05aed85f30bf88495bd89` (MD5 of "23232323")
- **Headers:**
  ```
  Content-Type: application/x-www-form-urlencoded
  app-token: 9120163167c05aed85f30bf88495bd89
  User-Agent: USER-AGENT-tvtap-APP-V2
  ```
- **Working Endpoints:**
  - `get_all_match_types` → Sport categories
  - `get_schedule_by_type` (POST: `type={id}`) → Events with channels
- **Problem:** `http_stream` values are DES-encrypted by native library
- **Key Found:** `ww23qq8811hh22aa` (16 bytes)
- **Status:** Schedule works, streams don't decrypt
- **File:** `lib/sources/sportsfire.py`
- **See:** `docs/SPORTSFIRE_NOTES.md` for full RE details

### 7. Streamfire ❌ DOWN
- **API Base:** `https://stfire.app/index.php?case=`
- **Status:** Returns success:0, appears to be offline

---

## POTENTIAL FUTURE SOURCES

### JetExtractors (from Torque Lite)
- **Module:** `script.module.jetextractors`
- **Description:** Sports scraper aggregator with multiple site extractors
- **Features:**
  - Unified interface for many sports streaming sites
  - Enable/disable specific extractors
  - Search across all sources
  - Progress dialogs during scraping
- **Integration:** Could add as dependency for more sources

### Additional XML Feeds
- one.sporthd.me - Channel data API
- liveon.sx/program - Alternative to super.league.do

---

## STREAM RESOLVERS

### wilderness.click (CRACKED) ✅
```python
# Algorithm in lib/resolvers/embed.py
def _resolve_wilderness_html(html):
    # 1. Extract base64 payload from script
    # 2. Base64 decode
    # 3. Split into 4 equal chunks
    # 4. Remove character at index 3 from each chunk
    # 5. Reorder chunks: [2, 0, 3, 1]
    # 6. Base64 decode each chunk
    # 7. Join all decoded chunks
    # 8. Base64 decode final result
    # 9. Parse JSON to get stream_url
```

### ResolveURL Integration ✅
- **File:** `lib/resolvers/resolveurl_resolver.py`
- **Supports:** Real-Debrid, Premiumize, AllDebrid
- **Error Tracking:** `_last_error` for dead link detection

### yt-dlp Fallback ✅
- **File:** `lib/resolvers/ytdlp.py`
- **Usage:** System yt-dlp in PATH
- **Fallback:** Uses ResolveURL if yt-dlp unavailable

---

## EMBED DOMAIN PATTERNS

Patterns extracted from sporthdme addon (may be useful for future sources):

| Domain | Method |
|--------|--------|
| dabac | api/player.php, base64 URL in hidden input |
| sansat | fid= pattern, document.write embed |
| istorm | iframe extraction |
| zvision | hlsjsConfig pattern |
| glisco | Similar to zvision |
| bedsport | get_content.php or api/player.php |
| coolrea | Clappr player with CHANNEL_KEY/BUNDLE auth |
| evfancy | Standard iframe |
| s2watch | player.setSrc pattern |
| vuen | new Player() pattern |
| gopst | Various patterns |

### Common Extraction Patterns
```python
# Pattern 1: fid= scripts
regex = r'<script>fid=[\'"](.+?)[\'"].+?src=[\'"](.+?)[\'"]></script>'

# Pattern 2: hlsjsConfig
# Look for data-page attribute with JSON containing streamData.streamurl

# Pattern 3: Clappr player
# Extract CHANNEL_KEY and BUNDLE from script
# Decode BUNDLE parts, construct auth_url, then server_lookup for stream

# Pattern 4: Direct m3u8
regex = r'(https?:\/\/[^\s]+\.m3u8)'

# Pattern 5: player.setSrc
regex = r'player.setSrc\(["\'](.+?)["\']\)'
```

---

## DEAD/OBFUSCATED SOURCES (NOT PURSUED)

| Source | Reason |
|--------|--------|
| SportzX APK | Native library obfuscation (liblive.so) |
| AK47Sports APK | ProGuard + NP protection |
| j1wizard.net | Just text file lists, YouTube-based |
| PurelyWrestling lists.py | Heavily obfuscated code |

---

## FILES REFERENCE

### Extracted APKs
```
/home/claude/sportsfire_arm7/                    # Sportsfire APK
/home/claude/sportsfire_arm7/lib/armeabi-v7a/libcompression.so  # Native crypto (25KB)
/home/claude/sportsfire_arm7/decompiled/         # JADX output
```

### Reference Kodi Addons
```
/home/claude/fod_extract/plugin.video.fod/
/home/claude/nflrewind_extract/plugin.video.nflrewind/
/home/claude/torque_ref/plugin.video.torquelite/  # JetExtractors patterns
/home/claude/torque_ref/plugin.video.torquelive/  # PitSport source
```

### Tools
```
/tmp/jadx/bin/jadx                               # Java decompiler v1.5.0
pip3: pycryptodome, capstone                     # Crypto/disasm tools
```

---

## NEXT STEPS FOR EXPANSION

### Priority 1: Sportsfire Decryption
- See `docs/SPORTSFIRE_NOTES.md`
- Options: Traffic capture, original APK, Frida hooks

### Priority 2: JetExtractors Integration
- Add `script.module.jetextractors` dependency
- Provides many additional sports sources

### Priority 3: Additional Resolvers
- More embed domain resolvers
- Clappr player support
- hlsjsConfig patterns
