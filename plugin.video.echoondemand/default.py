#!/usr/bin/env python3
"""
plugin.video.echoondemand — Echo OnDemand  v3.1.1
Kodi Omega (v21) plugin for browsing and playing VOD content (Movies and Series)
from an Xtream Codes IPTV service, plus three on-demand replay sources via debrid
(Wrestling Rewind, Wrestling on Demand, Fights on Demand) and a Live category
(Live Wrestling — WOD's live.xml feed; Sports Streams — curated Pluto TV
themed channels for golf, F1, UFC, MMA, boxing).

Changes in 3.1.1 (Pluto resolver fix — match browser exactly + diagnostics):
  - REWRITE: pluto.py now matches the Pluto web app's actual API usage,
    captured from a real Edge 147 browser request to boot.pluto.tv:
      * Param name change: channelID → channelSlug (we pass the channel ID
        as the value).  This is the critical fix — without channelSlug set,
        Pluto's boot endpoint returns a default/restricted response that
        doesn't include the user's regional channels.
      * appVersion bumped to current ('9.21.0-...')
      * deviceMake fixed: was 'firefox', now 'edge-chromium' (matches UA)
      * deviceVersion bumped to '147.0.0'
      * Added appLaunchCount and lastAppLaunchDate params
      * Removed the unused 'constraints' param the browser doesn't send
    Together these change the boot request from a guess-shape catalog fetch
    into a per-channel session mint, which is what the web player actually
    does and what Pluto's region-detection logic expects.
  - REWRITE: Boot is now per-channel rather than once-per-session.  Each
    channel ID gets its own cache entry (still 30-min TTL).  Network cost
    is one extra fetch per cold channel, paid once per 30 minutes.
  - HEADERS: Added Origin, Accept, Accept-Language, sec-ch-ua-*, sec-fetch-*,
    DNT — matching the browser's full header set so Pluto's edge filtering
    sees us as a real Edge tab rather than a bare Python urllib client.
  - UA: Bumped to Edge 147 / Chrome 147 with the Edg/147.0.0.0 suffix.
    This single constant (pluto.BROWSER_UA) is now used for both the boot
    request and the inputstream.adaptive stream/manifest headers, so
    everything Pluto sees from us has the same client identity.
  - DIAGNOSTIC: pluto.py now logs (via a callback bridge into xbmc.log)
    detailed info on resolver failure: top-level keys of the boot response,
    length of channels[] / EPG[] / channel arrays, a 400-char snippet of
    the response body, and the first channel entry's keys.  This lets us
    debug shape changes from the Kodi log without modifying code.
  - PARSE: Multi-shape response parsing — checks channels[] (current
    expected shape), EPG[] (some boot variants), and channel singular
    (likely shape for per-channel boot).  First match wins.

Changes in 3.1.0 (Pluto TV resolver + Sports Streams):
  - NEW: resources/lib/pluto.py — fetches a fresh session from boot.pluto.tv
    at play time and resolves channel IDs to current HLS manifest URLs.
    This fixes the WOD live.xml regional-retirement issue: stale session
    tokens baked into the upstream feed pointed some Pluto channels at
    "service no longer available" videos.  By minting our own session
    (matching the user's actual region) we get the live channel instead.
  - NEW: STATIC_MENUS['live_root'] now has two entries — 'Live Wrestling'
    (existing, walks WOD's live.xml) and 'Sports Streams' (new, curated
    list of seven Pluto TV themed sports channels: Golf Central, F1, UFC,
    Bellator, ONE, Top Rank Classics, DAZN Ringside).  Both routes
    resolve through pluto.py.
  - NEW: list_static_menu now supports a third entry kind: 'channel_id'
    entries become playable items routing to play_pluto.  This is what
    Sports Streams uses.  Existing 'wr_url' (folder → list_wr) and
    'menu_key' (folder → another static menu) entry kinds are unchanged.
  - NEW: play_pluto view — resolves a channel ID to a fresh URL via
    pluto.get_fresh_url, applies inputstream.adaptive properties (with the
    Pluto headers from v3.0.2), and plays.  Used by Sports Streams.
  - NEW: Setting `pluto_resolver_enabled` (bool, default true) — kill
    switch for the Pluto resolver.  If Pluto changes their boot API and
    the resolver breaks, the user can disable it without rolling back the
    addon.  When disabled, play_wr falls back to the original stitcher
    URL (current 3.0.2 behaviour) and play_pluto returns an error.
  - PIPELINE: play_wr now silently routes Pluto URLs through the new
    resolver before handing them to ISA.  Non-Pluto URLs (WWE Network
    CloudFront, debrid resolutions, etc.) are unchanged.  Resolver
    failure falls back to the original URL — worst case is identical to
    v3.0.2 behaviour.
  - CACHE: cache_clear_all now also wipes pluto.py's in-memory session
    cache.  "Refresh / Clear Cache" forces a fresh boot fetch on the
    next play.
  - ICONS: 6 new template-style PNGs in resources/images/genres/ for
    the Sports Streams entries (GOLF, F1, UFC, BELLATOR, ONE, BOXING).
    UFC and Boxing intentionally use new minimal-label icons rather than
    the existing 'UFC Replays' / 'Boxing Replays' icons — the new ones
    label the channel, not the action.

Changes in 3.0.2 (Pluto TV header fix + ISA cleanup):
  - FIX: Pluto TV channels (TNA WRESTLING 24/7, LUCHA LIBRE AAA 24/7, and
    similar in WOD's live.xml) were failing with HTTP 403 from the Pluto
    stitcher CDN.  Pluto's edge servers reject requests that don't look
    like they came from a web browser.  play_wr now sets inputstream.adaptive
    manifest_headers and stream_headers with a Chrome-shaped User-Agent and
    a pluto.tv Referer when the resolved URL is a Pluto stream.  Non-Pluto
    HLS streams (WWE Network from CloudFront, etc.) are left alone — the
    headers only apply when the URL contains pluto.tv.
  - CLEANUP: Dropped the deprecated `inputstream.adaptive.manifest_type=hls`
    property.  Kodi 21 (Omega) auto-detects manifest type from the response
    Content-Type / URL extension; setting it explicitly produced a
    deprecation warning in the Kodi log on every play.  Removing it
    silences that warning without changing behaviour.

Changes in 3.0.1 (live HLS fixes + audit):
  - FIX: play_wr now sets inputstream.adaptive properties when the resolved
    URL is HLS (.m3u8 manifests, Pluto TV stitcher URLs).  Kodi's built-in
    demuxer can fail on session-bound HLS streams with 'Error creating
    demuxer'; ISA's HLS handler is more forgiving.  No-op for direct
    mp4/mkv files; harmless if inputstream.adaptive isn't installed.
    The user-visible symptom this fixes: some live wrestling channels
    (notably some Pluto-backed ones like AEW) failing to play while
    others on the same feed worked fine.
  - FIX: list_wr log message no longer prints 'skipping item item' when an
    item-type entry has an empty link (cosmetic only — the skip itself
    was correct).
  - CONSISTENCY: wr_title default is now 'Wrestling Rewind' to match the
    root rename; previously the function signature still said 'Wrestling'.
    Only affects the fallback when no wr_title is passed (which the live
    code paths always do).

Changes in 3.0.0 (Live category, rename, settings backup, icon refresh):
  - NEW: Live category with sub-menu (STATIC_MENUS['live_root']).  Currently
    contains 'Live Wrestling' (WOD's live.xml feed).  FOD is a replay-only
    service upstream; Wrestling Rewind is also replay-only.  The parent menu
    is in place so future live sources are a STATIC_MENUS edit away.
  - RENAME: Root entry 'Wrestling' → 'Wrestling Rewind' for honest labeling.
    Each replay source now sits one click from the root menu, matching how
    Movies and Series are organised.  No URL change — bookmarks still work.
  - NEW: Backup / Restore Settings — two root menu entries that read/write a
    snapshot of all four user settings (username, password, buffer_secs,
    tmdb_api_key) to special://userdata/echoondemand_settings.json.  This
    file lives one level up from the addon's own userdata directory and
    survives a full uninstall.  Useful for users who install fresh zips
    instead of using Kodi's update flow.
  - ICONS: 17 new/refreshed icons in resources/images/genres/.  TNA, NWA,
    NJPW, ROH, RPW, INDY, MMA, LIVE, LIVE WRESTLING, WRESTLEMANIA, PPV,
    DOCS, LATEST, FREE, WOD, FOD all match the existing template style.
    The blank-placeholder Wrestling.png is now a proper 'WRESTLING' icon.
  - STATIC_MENUS: icon_label fields updated to point at the new icons where
    appropriate.  No structural change — same dispatch model.
  - DOCS: README and HANDOFF cover the upgrade flow explicitly.  Kodi
    preserves userdata across 'Install from zip' over an existing addon,
    but 'Uninstall' (then reinstall) wipes it.  The new Backup/Restore
    feature is the safety net for the latter case.

Changes in 2.6.0 (audit + WOD/FOD integration):
  - NEW: Wrestling on Demand (WOD) section.  Curated category tree pointing at
    individual MicroJen XML feeds on l3grthu.com/hades/wod21.  Covers WWE
    (RAW, SmackDown, NXT, WrestleMania, PPV), other promotions (AEW, TNA,
    NWA, NJPW, ROH, RPW, Indy), documentaries, interviews, and archive.
    No live content (deliberately scoped to on-demand).
  - NEW: Fights on Demand (FOD) section.  UFC PPV, Fight Night, ESPN/ABC/FOX/FUEL,
    Classic, Shows; MMA; Boxing; plus a Free (No Debrid) sub-menu.  Sources
    XML feeds from mylostsoulspace.co.uk/FightsOnDemand.
  - NEW: STATIC_MENUS / list_static_menu() — single mechanism that drives both
    new sections.  Each leaf is a dir item that hands off to the existing
    list_wr() / play_wr() flow.  Adding a new section in the future is a
    pure-data change to STATIC_MENUS, no new view code required.
  - PARSER: wrestling.py now aliases <summaru> to 'summary' (WOD typo).
  - PARSER: wrestling.py adds strip_format_tags() utility for cleaning Kodi
    BBCode-style noise out of WOD/FOD titles for display.
  - BUG FIX: list_wr now skips item-type entries with empty links (previously
    only dir-type entries were skipped — items with empty links would appear
    in the list but show "No playable link" on click).
  - BUG FIX: list_wr handles the case where a dir-type entry has a list of
    links (takes the first); previously this would urlencode the list into
    a broken navigation URL.
  - IMPROVEMENT: list_wr uses item-level thumbnail/fanart when present, falling
    back to ADDON_ICON / ADDON_FANART.  Wrestling Rewind feeds rarely populate
    these fields so the previous code was fine for that source; WOD/FOD feeds
    are rich in artwork.
  - IMPROVEMENT: list_wr sets Plot via InfoTagVideo for items with a summary,
    so the user can press Info and see context.  setContent('files') is
    unchanged so right-side info panel suppression still works in Aeon Nox Silvo.
  - IMPROVEMENT: list_wr strips format tags from titles for clean display.
  - BUG FIX: cache_clear_all() now preserves tmdb_fanart.json.  This cache is
    independent of the IPTV / wrestling / fights caches and represents many
    plays of accumulated work.  Was documented as a known limitation in v2.5.0.

Changes in 2.5.0 (audit + bugfix sweep):
  - BUG FIX: list_root() no longer gates on credentials_ok(). Wrestling is
    accessible even when IPTV credentials are not configured. Each IPTV
    section (list_movie_categories, list_series_categories) already does its
    own credentials check — the root-level check was redundant and blocked
    unrelated content.
  - BUG FIX: All list_* exception return paths now call
    endOfDirectory(HANDLE, succeeded=False) before returning. Previously,
    every network/parse error left Kodi hanging in an infinite loading state
    waiting for a directory response that never came. Affected:
    list_movie_categories, list_movies, list_series_categories, list_series,
    list_seasons, list_episodes.
  - BUG FIX: credentials_ok() failure paths in list_movie_categories and
    list_series_categories now call endOfDirectory(succeeded=False) for the
    same reason.
  - BUG FIX: list_wr() now skips dir items with empty link fields rather than
    building a wr_url='' navigation URL that silently produces zero items.
  - CLEANUP: import base64 moved to module-level. Redundant inline
    `import base64` / `import json` removed from list_wr() and play_wr().

Changes in 2.4.x (Wrestling UI consistency):
  - Wrestling root entry uses ADDON_ICON like Movies and Series (no custom icon).
  - list_wr: setContent('files') suppresses info panel; no VideoInfoTag calls.
  - play_wr: no VideoInfoTag, no art on resolved ListItem.
  - do_refresh: calls list_root(update_listing=True) so the Refresh URL is
    replaced in-place in Kodi's navigation stack, preventing the cache-clear
    notification from firing again on back-navigation.
  - Wrestling.png genre icon added (unused by current code, available for future).

Changes in 2.3.x (wrestling parser audit):
  - _strip_preamble: regex now handles both <layouttype> and <layoutype> variants
    (PPV feeds use single-t close tag).
  - parse_xml: pass 4 added — per-item lenient regex extraction for feeds where
    overall document structure is broken but individual items are valid XML.
  - _strip_label_suffix: now handles any URI scheme (magnet:, http:, etc.) not
    just http prefix. Previously magnet: labels were not stripped.
  - normalise_links: now includes magnet: URIs for Real-Debrid torrent resolution.
    Previously magnet links were silently dropped.
  - _collect_items: wrapper detection is now generic. Previous code only
    recognised <xml> as an intermediate wrapper, silently returning [] for PPV
    feeds that use a different wrapper element name.
  - parse_feed: mutual XML/JSON fallback when primary parser returns empty.
  - All resolution and parse outcomes logged at LOGINFO (visible without debug mode).
  - resolve_best_link: _url_from_resolved() handles both plain string and
    ResolvedURL object; embeds headers in Kodi's native pipe format.

Changes in 2.2.x (Wrestling Rewind integration, sublink nesting fix):
  - Wrestling section added to root menu.
  - resources/lib/wrestling.py: pure data layer — HTTP fetch, MicroJen XML/JSON
    parse, cache, debrid resolution via resolveurl.
  - Debrid is always attempted first; direct-link fallback is silent.
  - _parse_element: two-pass sublink extraction handles both direct-child and
    nested-inside-<link> sublink patterns (WR's own parser uses .//sublink).
  - Pre-buffer applies to Wrestling playback using same setting as IPTV.
  - script.module.resolveurl added as hard dependency in addon.xml.

Changes in 2.0.0 (final IPTV polish pass):
  - list_root setContent changed 'videos' → 'addons' (suppresses episode info panel).
  - Companion skin edits (MyVideoNav.xml, View_50_List.xml): info panel suppressed
    for category views; duplicate label removed; ghost control reference removed.

Changes in 1.3.x (audit + cosmetic):
  - credentials_ok() guard added to category views for deep-link safety.
  - cat_name threaded through URL params for correct breadcrumb display.
  - list_series, list_episodes: empty-list guards added.
  - list_seasons: setContent 'tvshows' → 'seasons'.
  - Refresh entry isFolder corrected False → True.
  - play_movie: TMDB fetch moved to after _apply_buffer.

Routing:
  (root)                                    -> list_root()
  mode=movie_cats                           -> list_movie_categories()
  mode=movies       cat_id=X  cat_name=Y   -> list_movies(cat_id, cat_name)
  mode=series_cats                          -> list_series_categories()
  mode=series       cat_id=X  cat_name=Y   -> list_series(cat_id, cat_name)
  mode=seasons      series_id=X            -> list_seasons(series_id)
  mode=episodes     series_id=X  season=N  -> list_episodes(series_id, season_num)
  mode=play_movie   vod_id=X  ext=Y        -> play_movie(vod_id, ext)
  mode=play_episode ep_id=X   ext=Y        -> play_episode(ep_id, ext)
  mode=wr_list      wr_url=X [wr_title=Y]  -> list_wr(wr_url, wr_title)
  mode=wr_play      wr_item=X              -> play_wr(wr_item)
  mode=static_menu  key=K  title=T         -> list_static_menu(key, title)
                                              (drives WOD, FOD, and Live trees)
  mode=play_pluto   channel_id=C  title=T  -> play_pluto(channel_id, title)
                                              (Sports Streams entries)
  mode=settings_backup                      -> do_settings_backup()
  mode=settings_restore                     -> do_settings_restore()
  mode=refresh                             -> clear all cache, reload root

Cache strategy (all files in addon profile directory):
  movie_cats.json          TTL 1 hour   -- movie genre category list
  series_cats.json         TTL 1 hour   -- series genre category list
  movies_{cat_id}.json     TTL 30 min   -- movie list for one category
  series_{cat_id}.json     TTL 30 min   -- series list for one category
  seriesinfo_{id}.json     TTL 1 hour   -- full season/episode data for one series
  tmdb_fanart.json         permanent    -- TMDB backdrop URL cache (key = name|year)
  wr_{url_hash}.json       TTL 30 min   -- Wrestling feed cache (managed by wrestling.py)

Stream URL formats (standard Xtream Codes):
  Movie:   {SERVER}/movie/{user}/{pass}/{vod_id}.{ext}
  Episode: {SERVER}/series/{user}/{pass}/{episode_id}.{ext}

Assumptions:
  - Service is Xtream Codes-compatible (player_api.php supported).
  - Extension (.mkv, .mp4, etc.) comes from the API field 'container_extension'.
  - All IPTV artwork URLs come from the API. Nothing is generated locally.
  - script.module.resolveurl is installed and configured with a debrid account.
  - Kodi Omega (v21) / Python 3.
"""

import sys
import json
import os
import time
import glob
import base64
from urllib.parse import parse_qsl, urlencode, quote
from urllib.request import urlopen, Request

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from resources.lib import wrestling as _wr
from resources.lib import pluto     as _pluto

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

ADDON    = xbmcaddon.Addon()
HANDLE   = int(sys.argv[1])
BASE_URL = sys.argv[0]
LOG_TAG  = '[EchoOD]'

SERVER  = 'https://blueonesuperoceanhere.com'
API_URL = '{}/player_api.php'.format(SERVER)

TTL_CATEGORIES = 3600   # 1 hour  -- category lists rarely change
TTL_STREAMS    = 1800   # 30 min  -- stream lists per category
TTL_SERIESINFO = 3600   # 1 hour  -- full season/episode data per series

# TMDB — used for movie fanart/backdrop enrichment at play time.
# Free API key required; register at https://www.themoviedb.org/settings/api
# Rate limit: 40 req/10s — very permissive for personal use.
TMDB_API      = 'https://api.themoviedb.org/3'
TMDB_IMG_BASE = 'https://image.tmdb.org/t/p/w1280'   # good balance of size vs quality

# Addon-level artwork — resolved once at import time.
# Build paths from the addon's own directory rather than relying solely on
# getAddonInfo('fanart'/'icon'), which requires an <assets> block in addon.xml
# to return non-empty values (added in 1.0.7). Both methods are tried so the
# code works even if the assets block is absent for some reason.
def _resolve_addon_art(filename):
    """Return the filesystem path to an artwork file in the addon root."""
    addon_path = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
    if isinstance(addon_path, bytes):
        addon_path = addon_path.decode('utf-8')
    return os.path.join(addon_path, filename)

# Resolved once at import — used for artwork and bundled genre icon lookups.
ADDON_PATH   = _resolve_addon_art('')          # addon root dir, trailing sep
ADDON_FANART = _resolve_addon_art('fanart.jpg')
ADDON_ICON   = _resolve_addon_art('icon.png')


# ---------------------------------------------------------------------------
# Wrestling on Demand (WOD) and Fights on Demand (FOD) — static category trees
# ---------------------------------------------------------------------------
# Both sources use the same MicroJen XML format that resources/lib/wrestling.py
# already handles.  Neither has a single master menu XML on the upstream side
# (WOD's l3grthu.com only serves leaf XMLs; FOD's fodmain-new.xml exists but
# carries BBCode noise in its labels).  So we curate the menu structure here
# in pure data and dispatch into the existing list_wr / play_wr flow.
#
# Each entry is one of:
#   {'title': <label>, 'wr_url': <feed XML>, 'icon_label': <bundled icon match>}
#       Renders as a folder.  Clicking enters list_wr against that XML.
#       icon_label is matched against bundled PNG names in
#       resources/images/genres/; missing match → ADDON_ICON.
#   {'title': <label>, 'menu_key': <STATIC_MENUS key>}
#       Renders as a folder.  Clicking enters another static menu.
#
# Editing this dict is the only change needed to add/remove a feed.
# No view code or routing changes required.

WOD_BASE = 'https://l3grthu.com/hades/wod21'
FOD_BASE = 'https://mylostsoulspace.co.uk/FightsOnDemand'

STATIC_MENUS = {
    # ---------- Wrestling on Demand ----------
    'wod_root': [
        {'title': 'WWE',                  'menu_key':   'wod_wwe'},
        {'title': 'Other Promotions',     'menu_key':   'wod_other'},
        {'title': 'Documentaries',        'wr_url':     WOD_BASE + '/documentaries/docmain.xml',
                                          'icon_label': 'Documentary'},
        {'title': 'Interviews & Kayfabe', 'wr_url':     WOD_BASE + '/kayfabe/main.xml'},
        {'title': 'Special Matches',      'wr_url':     WOD_BASE + '/specialmatches/specialmatches.xml'},
        {'title': 'Random Events',        'wr_url':     WOD_BASE + '/latestshows/randomevents.xml'},
        {'title': 'Movies & TV',          'wr_url':     WOD_BASE + '/mov.xml'},
        {'title': 'Archive',              'wr_url':     WOD_BASE + '/Archives/archives.xml'},
    ],
    'wod_wwe': [
        {'title': 'RAW',                  'wr_url':     WOD_BASE + '/latestshows/raw.xml',
                                          'icon_label': 'WWE RAW'},
        {'title': 'SmackDown',            'wr_url':     WOD_BASE + '/latestshows/smackdown.xml',
                                          'icon_label': 'WWE SmackDown'},
        {'title': 'NXT',                  'wr_url':     WOD_BASE + '/latestshows/nxtmain.xml',
                                          'icon_label': 'NXT'},
        {'title': 'Latest Shows',         'wr_url':     WOD_BASE + '/latestshows/latestshows.xml',
                                          'icon_label': 'Latest Shows'},
        {'title': 'WrestleMania',         'wr_url':     WOD_BASE + '/wrestlemania/mainwm.xml',
                                          'icon_label': 'WrestleMania'},
        {'title': 'PPV Events',           'wr_url':     WOD_BASE + '/ppv/ppvmain.xml',
                                          'icon_label': 'PPV Events'},
        {'title': 'WWE YouTube',          'wr_url':     WOD_BASE + '/wweyt.xml'},
    ],
    'wod_other': [
        {'title': 'AEW',                  'wr_url':     WOD_BASE + '/aew/aewppv.xml',
                                          'icon_label': 'AEW'},
        {'title': 'TNA / Impact',         'wr_url':     WOD_BASE + '/tna/tnamain.xml',
                                          'icon_label': 'TNA'},
        {'title': 'NWA',                  'wr_url':     WOD_BASE + '/nwa/main.xml',
                                          'icon_label': 'NWA'},
        {'title': 'NJPW',                 'wr_url':     WOD_BASE + '/njpw/njpwmain.xml',
                                          'icon_label': 'NJPW'},
        {'title': 'ROH',                  'wr_url':     WOD_BASE + '/roh/main.xml',
                                          'icon_label': 'ROH'},
        {'title': 'RPW',                  'wr_url':     WOD_BASE + '/random/rpw.xml',
                                          'icon_label': 'RPW'},
        {'title': 'Indy Wrestling',       'wr_url':     WOD_BASE + '/indy.xml',
                                          'icon_label': 'Indy Wrestling'},
    ],

    # ---------- Fights on Demand ----------
    'fod_root': [
        {'title': 'Latest UFC / MMA',     'wr_url':     FOD_BASE + '/latestufc-mmaevents.xml',
                                          'icon_label': 'UFC Replays'},
        {'title': 'UFC Events',           'menu_key':   'fod_ufc'},
        {'title': 'MMA Events',           'wr_url':     FOD_BASE + '/mmaevents/mmaeventreplaysmain-new.xml',
                                          'icon_label': 'MMA'},
        {'title': 'Boxing',               'wr_url':     FOD_BASE + '/boxing/boxingreplays-new.xml',
                                          'icon_label': 'Boxing Replays'},
        {'title': 'Free (No Debrid)',     'menu_key':   'fod_free'},
    ],
    'fod_ufc': [
        {'title': 'UFC PPV',              'wr_url':     FOD_BASE + '/ufcevents/ufcppv-new.xml',
                                          'icon_label': 'UFC Replays'},
        {'title': 'UFC Fight Night',      'wr_url':     FOD_BASE + '/ufcevents/ufcfightnightreplays-new.xml'},
        {'title': 'UFC on ESPN',          'wr_url':     FOD_BASE + '/ufcevents/ufcfightnightonespn-new.xml'},
        {'title': 'UFC on ABC',           'wr_url':     FOD_BASE + '/ufcevents/ufconabc-new.xml'},
        {'title': 'UFC on FOX',           'wr_url':     FOD_BASE + '/ufcevents/ufconfoxtv-new.xml'},
        {'title': 'UFC on FUEL',          'wr_url':     FOD_BASE + '/ufcevents/ufconfueltv-new.xml'},
        {'title': 'UFC BJJ',              'wr_url':     FOD_BASE + '/ufcevents/ufcbjj-new.xml'},
        {'title': 'UFC Shows & Series',   'wr_url':     FOD_BASE + '/ufcshows/ufcshowsmain-new.xml'},
        {'title': 'Classic UFC PPV',      'wr_url':     FOD_BASE + '/ufcevents/classicufc-new.xml'},
        {'title': 'Classic UFC Fight Night',
                                          'wr_url':     FOD_BASE + '/ufcevents/classicfightnight-new.xml'},
        {'title': 'UFC Events Main',      'wr_url':     FOD_BASE + '/ufcevents/ufceventreplaysmain-new.xml'},
    ],
    'fod_free': [
        {'title': 'Free UFC',             'wr_url':     FOD_BASE + '/nondebridufc.xml',
                                          'icon_label': 'Free'},
        {'title': 'Free MMA',             'wr_url':     FOD_BASE + '/nondebridmmareplays.xml',
                                          'icon_label': 'Free'},
        {'title': 'Free Boxing',          'wr_url':     FOD_BASE + '/boxing/boxingreplays-nondebrid.xml',
                                          'icon_label': 'Boxing Replays'},
    ],

    # ---------- Live ----------
    # Two sub-categories: 'Live Wrestling' walks WOD's live.xml feed (which
    # has its own dynamic channel list maintained upstream), and 'Sports
    # Streams' walks our curated list of Pluto TV themed sports channels.
    # Both ultimately resolve through pluto.py — wrestling channels are
    # routed there transparently in play_wr, and Sports Streams entries
    # use the dedicated play_pluto view by channel ID.
    'live_root': [
        {'title': 'Live Wrestling',       'wr_url':     WOD_BASE + '/live.xml',
                                          'icon_label': 'Live Wrestling'},
        {'title': 'Sports Streams',       'menu_key':   'live_sports',
                                          'icon_label': 'Live'},
    ],

    # ---------- Sports Streams (Pluto TV channels, curated) ----------
    # 24/7 themed sports channels.  Each entry is rendered by list_static_menu
    # but with a 'channel_id' field that triggers the play_pluto branch
    # instead of a sub-menu navigation.  Adding a channel is a one-line
    # edit — find the channel ID in the pluto.tv URL bar (the 24-char hex
    # in /us/live-tv/<id>) and add an entry below.
    'live_sports': [
        {'title': 'Golf Central',         'channel_id': '65493029ab052400089e9d2f',
                                          'icon_label': 'Golf'},
        {'title': 'F1 Channel',           'channel_id': '65c69ee3d77d450008c80438',
                                          'icon_label': 'F1'},
        {'title': 'UFC',                  'channel_id': '677d9adfa9a51b0008497fa0',
                                          'icon_label': 'UFC'},
        {'title': 'Bellator MMA',         'channel_id': '5ebc8688f3697d00072f7cf8',
                                          'icon_label': 'Bellator'},
        {'title': 'ONE Championship',     'channel_id': '668c5d3bfd9eb2000882bb50',
                                          'icon_label': 'ONE'},
        {'title': 'Top Rank Classics',    'channel_id': '64d160f53c785e0008df525e',
                                          'icon_label': 'Boxing'},
        {'title': 'DAZN Ringside',        'channel_id': '649b6898f2ec0000081a9460',
                                          'icon_label': 'Boxing'},
    ],
}


def _menu_icon(label):
    """
    Return the bundled icon path for a menu entry's icon_label, or ADDON_ICON
    if no bundled match exists.  Stays inside resources/images/genres/ —
    does not consult the optional moviegenreicons resource addon and does not
    fall back to DefaultGenre.png.  Keeps the WOD/FOD menu look uniform with
    the rest of Echo OnDemand.
    """
    if not label:
        return ADDON_ICON
    bundled = os.path.join(ADDON_PATH, 'resources', 'images', 'genres',
                           '{}.png'.format(label.strip()))
    return bundled if os.path.exists(bundled) else ADDON_ICON


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('{} {}'.format(LOG_TAG, msg), level)


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------

def build_url(**kwargs):
    return '{}?{}'.format(BASE_URL, urlencode(kwargs))


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def get_credentials():
    return (
        ADDON.getSetting('username').strip(),
        ADDON.getSetting('password').strip(),
    )


def credentials_ok():
    u, p = get_credentials()
    if not u or not p:
        xbmcgui.Dialog().ok(
            'Echo OnDemand',
            'Please enter your username and password in Settings.'
        )
        ADDON.openSettings()
        return False
    return True


# ---------------------------------------------------------------------------
# Xtream Codes API
# ---------------------------------------------------------------------------

def api_get(action, extra_params=None):
    """
    Call player_api.php and return parsed JSON.
    Raises URLError on network failure, ValueError if response is not JSON.
    """
    username, password = get_credentials()
    params = {'username': username, 'password': password, 'action': action}
    if extra_params:
        params.update(extra_params)

    url = '{}?{}'.format(API_URL, urlencode(params))
    log('API: action={} extra={}'.format(action, extra_params))
    req = Request(url, headers={'User-Agent': 'Kodi/EchoOnDemand'})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _profile_dir():
    path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path(key):
    safe_key = key.replace('/', '_').replace('\\', '_')
    return os.path.join(_profile_dir(), '{}.json'.format(safe_key))


def cache_load(key, ttl):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        age = time.time() - data.get('ts', 0)
        if age < ttl:
            log('Cache hit: {} (age {:.0f}s)'.format(key, age))
            return data['payload']
        log('Cache expired: {} (age {:.0f}s)'.format(key, age))
    except Exception as e:
        log('Cache read error ({}): {}'.format(key, e), xbmc.LOGWARNING)
    return None


def cache_save(key, payload):
    path = _cache_path(key)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'ts': time.time(), 'payload': payload}, f)
        log('Cache saved: {}'.format(key))
    except Exception as e:
        log('Cache write error ({}): {}'.format(key, e), xbmc.LOGWARNING)


def cache_clear_all():
    """
    Delete all *.json cache files in the profile dir.

    EXCEPTION: tmdb_fanart.json is preserved.  It accumulates over many movie
    plays (one TMDB lookup per unique movie name|year), and is independent of
    the IPTV / wrestling / fights caches that users actually want to clear.
    There's a separate path to wipe it deliberately if ever needed.
    """
    pattern = os.path.join(_profile_dir(), '*.json')
    for path in glob.glob(pattern):
        if os.path.basename(path) == 'tmdb_fanart.json':
            continue
        try:
            os.remove(path)
            log('Deleted cache: {}'.format(os.path.basename(path)))
        except Exception as e:
            log('Could not delete {}: {}'.format(path, e), xbmc.LOGWARNING)
    # Wipe the in-memory Pluto session cache too — next play_pluto / play_wr
    # against a Pluto channel will fetch a fresh boot response.
    _pluto.clear_session_cache()
    log('Pluto session cache cleared')


# ---------------------------------------------------------------------------
# TMDB fanart cache
# ---------------------------------------------------------------------------
# Separate persistent store for TMDB backdrop URLs, keyed by "name|year".
# Populated lazily at play time — zero overhead on list loading.
# File lives alongside other cache files in the addon profile directory.

def _tmdb_key():
    """Return the TMDB API key from settings, or '' if not configured."""
    return ADDON.getSetting('tmdb_api_key').strip()


def _tmdb_cache_key(name, year):
    return '{}|{}'.format(name.lower().strip(), int(year) if year else 0)


def _load_tmdb_cache():
    path = os.path.join(_profile_dir(), 'tmdb_fanart.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_tmdb_cache(cache):
    path = os.path.join(_profile_dir(), 'tmdb_fanart.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
    except Exception as e:
        log('TMDB cache save error: {}'.format(e), xbmc.LOGWARNING)


def fetch_and_cache_tmdb_fanart(name, year):
    """
    Search TMDB for a movie by name+year, cache and return its backdrop URL.
    Called after _apply_buffer in play_movie — the plugin process stays alive
    after setResolvedUrl so this runs while the stream is already playing.
    Returns '' on any failure (missing key, network error, no results).
    """
    api_key = _tmdb_key()
    if not api_key or not name:
        return ''

    cache = _load_tmdb_cache()
    key   = _tmdb_cache_key(name, year)

    # Already cached — return immediately, even if empty (means TMDB had nothing)
    if key in cache:
        return cache[key]

    backdrop = ''
    try:
        params = {'api_key': api_key, 'query': name, 'language': 'en-US'}
        if year:
            params['year'] = int(year)
        url = '{}/search/movie?{}'.format(TMDB_API, urlencode(params))
        req = Request(url, headers={'User-Agent': 'Kodi/EchoOnDemand'})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='ignore'))
        results = data.get('results', [])
        if results and results[0].get('backdrop_path'):
            backdrop = TMDB_IMG_BASE + results[0]['backdrop_path']
            log('TMDB fanart found for "{}": {}'.format(name, backdrop))
        else:
            log('TMDB: no backdrop for "{}"'.format(name))
    except Exception as e:
        log('TMDB lookup error for "{}": {}'.format(name, e), xbmc.LOGWARNING)

    # Cache the result (even '' so we don't retry on every play)
    cache[key] = backdrop
    _save_tmdb_cache(cache)
    return backdrop


# ---------------------------------------------------------------------------
# Data fetching (with caching)
# ---------------------------------------------------------------------------

def get_movie_categories():
    cached = cache_load('movie_cats', TTL_CATEGORIES)
    if cached is not None:
        return cached
    data = api_get('get_vod_categories')
    if not isinstance(data, list):
        raise ValueError('Unexpected response from get_vod_categories')
    cache_save('movie_cats', data)
    return data


def get_series_categories():
    cached = cache_load('series_cats', TTL_CATEGORIES)
    if cached is not None:
        return cached
    data = api_get('get_series_categories')
    if not isinstance(data, list):
        raise ValueError('Unexpected response from get_series_categories')
    cache_save('series_cats', data)
    return data


def get_movies_for_category(cat_id):
    key = 'movies_{}'.format(cat_id)
    cached = cache_load(key, TTL_STREAMS)
    if cached is not None:
        return cached
    data = api_get('get_vod_streams', {'category_id': cat_id})
    if not isinstance(data, list):
        raise ValueError('Unexpected response from get_vod_streams')
    cache_save(key, data)
    return data


def get_series_for_category(cat_id):
    key = 'series_{}'.format(cat_id)
    cached = cache_load(key, TTL_STREAMS)
    if cached is not None:
        return cached
    data = api_get('get_series', {'category_id': cat_id})
    if not isinstance(data, list):
        raise ValueError('Unexpected response from get_series')
    cache_save(key, data)
    return data


def get_series_info(series_id):
    """
    Returns the full series dict from the API:
      info     -> {name, plot, cast, genre, releaseDate, cover, backdrop_path, ...}
      seasons  -> [{season_number, name, cover, ...}, ...]
      episodes -> {'1': [{id, title, container_extension, episode_num,
                          info: {plot, movie_image, duration_secs, ...}}, ...], ...}
    """
    key = 'seriesinfo_{}'.format(series_id)
    cached = cache_load(key, TTL_SERIESINFO)
    if cached is not None:
        return cached
    data = api_get('get_series_info', {'series_id': series_id})
    if not isinstance(data, dict):
        raise ValueError('Unexpected response from get_series_info')
    cache_save(key, data)
    return data


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def make_art(thumb='', fanart='', poster=''):
    """
    Build an art dict for a list item.

    Fanart priority:
      1. Item-level fanart passed in (series backdrop, episode backdrop, etc.)
      2. ADDON_FANART — the Echo OnDemand default background, used when no
         item-specific fanart is available (movies, genre categories, etc.)
    """
    art = {}
    if thumb:
        art['thumb'] = thumb
    art['fanart'] = fanart if fanart else ADDON_FANART
    if poster:
        art['poster'] = poster
    if thumb and 'poster' not in art:
        art['poster'] = thumb
    return art


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_duration(raw):
    """Return duration as int seconds. Accepts int/float or 'hh:mm:ss' strings."""
    if not raw:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        parts = raw.strip().split(':')
        try:
            return sum(
                int(p) * (60 ** (len(parts) - 1 - i))
                for i, p in enumerate(parts)
            )
        except ValueError:
            return 0
    return 0


def make_cast(raw_cast):
    """
    Convert API cast (comma-separated string or list) to list[xbmc.Actor].
    Omega's InfoTagVideo.setCast() requires xbmc.Actor objects -- plain strings
    cause a TypeError that silently kills the list item in some builds.
    """
    if not raw_cast:
        return []
    if isinstance(raw_cast, list):
        names = [str(n).strip() for n in raw_cast if str(n).strip()]
    else:
        names = [n.strip() for n in str(raw_cast).split(',') if n.strip()]
    return [xbmc.Actor(name=n, role='', order=i, thumbnail='')
            for i, n in enumerate(names)]


# ---------------------------------------------------------------------------
# Genre icon resolution
# ---------------------------------------------------------------------------
# Priority order:
#   1. resource.images.moviegenreicons.transparent — if the user has it installed,
#      it provides clean per-genre PNGs and is the best option.
#   2. Hand-rolled fallback map to Kodi built-in icons for a few broad types.
#   3. DefaultGenre.png — always available, safe fallback.
#
# The resource addon uses title-cased filenames: Action.png, Comedy.png, etc.
# We normalise the genre name to title-case before probing.

_GENRE_RESOURCE_ADDON = 'resource.images.moviegenreicons.transparent'

# Kodi built-in icon fallbacks for genres that have a rough match.
_GENRE_BUILTIN_MAP = {
    'action':               'DefaultMovieTitle.png',
    'action & adventure':   'DefaultMovieTitle.png',
    'animation':            'DefaultMovies.png',
    'documentary':          'DefaultMovies.png',
    'family':               'DefaultMovies.png',
    'music':                'DefaultMusicVideos.png',
    'music videos':         'DefaultMusicVideos.png',
    'tv movie':             'DefaultTVShows.png',
}


def get_genre_icon(genre_name):
    """
    Return the best available icon path for genre_name.

    Probe order:
      1. Bundled icons in resources/images/genres/{name}.png — always present.
      2. resource.images.moviegenreicons.transparent — if installed.
      3. Hand-rolled Kodi built-in fallback map.
      4. DefaultGenre.png.

    Uses the module-level ADDON_PATH constant — no repeated translatePath calls.
    """
    normalised = genre_name.strip().title()

    # 1. Bundled icon
    bundled = os.path.join(ADDON_PATH, 'resources', 'images', 'genres',
                           '{}.png'.format(genre_name.strip()))
    if os.path.exists(bundled):
        return bundled
    bundled_tc = os.path.join(ADDON_PATH, 'resources', 'images', 'genres',
                              '{}.png'.format(normalised))
    if os.path.exists(bundled_tc):
        return bundled_tc

    # 2. External resource addon
    for candidate in (normalised, genre_name.strip()):
        resource_path = 'special://home/addons/{}/resources/{}.png'.format(
            _GENRE_RESOURCE_ADDON, candidate
        )
        if os.path.exists(xbmcvfs.translatePath(resource_path)):
            return resource_path

    # 3. Kodi built-in fallback
    log('Genre icon MISS for "{}": using built-in fallback'.format(genre_name))
    return _GENRE_BUILTIN_MAP.get(genre_name.strip().lower(), 'DefaultGenre.png')


# ---------------------------------------------------------------------------
# Context menu helpers
# ---------------------------------------------------------------------------

def _ctx_movie():
    """Context menu items for a playable movie entry."""
    return [
        ('Mark as Watched',    'Action(ToggleWatched)'),
        ('Movie Information',  'Action(Info)'),
        ('Add to Queue',       'Action(Queue)'),
    ]


def _ctx_episode():
    """Context menu items for a playable episode entry."""
    return [
        ('Mark as Watched',    'Action(ToggleWatched)'),
        ('Episode Information','Action(Info)'),
        ('Add to Queue',       'Action(Queue)'),
    ]


def _ctx_tvshow():
    """Context menu items for a TV show folder."""
    return [
        ('Show Information',   'Action(Info)'),
    ]


# ---------------------------------------------------------------------------
# Pre-buffer playback
# ---------------------------------------------------------------------------

def get_buffer_secs():
    """Read pre-buffer seconds from addon settings. Returns 5 if unset/invalid."""
    try:
        return max(0, int(float(ADDON.getSetting('buffer_secs') or '5')))
    except (ValueError, TypeError):
        return 5


def _apply_buffer(buffer_secs):
    """
    Called AFTER setResolvedUrl. The plugin process stays alive until Python
    exits, giving us a window to intercept the player.

    Strategy:
      1. Poll until xbmc.Player.isPlaying() — up to 12 seconds.
      2. Pause.
      3. Sleep buffer_secs silently — no toast, no dialog.
      4. Resume — but only if the player is still paused.
         xbmc.Player.isPaused() does NOT exist in Kodi Omega; use
         xbmc.getCondVisibility('Player.Paused') instead.

    If the player never starts (stream error) bail silently.
    """
    if buffer_secs <= 0:
        return

    player  = xbmc.Player()
    monitor = xbmc.Monitor()

    # Wait up to 12 s for playback to begin
    poll_ms   = 250
    timeout_s = 12
    waited    = 0
    while waited < timeout_s:
        if monitor.abortRequested():
            return
        if player.isPlaying():
            break
        xbmc.sleep(poll_ms)
        waited += poll_ms / 1000.0

    if not player.isPlaying():
        log('_apply_buffer: player did not start within {}s — skipping'.format(timeout_s),
            xbmc.LOGWARNING)
        return

    log('_apply_buffer: pausing for {}s'.format(buffer_secs))
    player.pause()

    # Sleep silently — no toast, cleaner UX.
    # The player simply pauses briefly then resumes; user sees no interruption dialog.
    elapsed   = 0
    target_ms = buffer_secs * 1000
    while elapsed < target_ms:
        if monitor.abortRequested():
            return
        xbmc.sleep(200)
        elapsed += 200

    # xbmc.Player.isPaused() does not exist in Kodi Omega — use getCondVisibility.
    # Only resume if we're still paused; if the user hit play manually, leave them alone.
    if xbmc.getCondVisibility('Player.Paused'):
        player.pause()
        log('_apply_buffer: resumed')


# ---------------------------------------------------------------------------
# InfoTagVideo setters (Omega-compatible)
# ---------------------------------------------------------------------------
# In Kodi 20+ (Nexus/Omega), ListItem.setInfo('video', {...}) is deprecated.
# Use getVideoInfoTag() and set fields via the InfoTagVideo object instead.
# Keeping these as small helpers keeps the view functions readable.

def _tag_movie(li, name, year=0, rating=0.0, plot='',
               cast=None, director='', genre='', runtime=0):
    tag = li.getVideoInfoTag()
    tag.setMediaType('movie')
    tag.setTitle(name)
    if year:
        tag.setYear(year)
    if rating:
        tag.setRating(rating)
    if plot:
        tag.setPlot(plot)
    if cast:
        tag.setCast(cast)
    if director:
        tag.setDirectors([d.strip() for d in director.split(',') if d.strip()])
    if genre:
        tag.setGenres([g.strip() for g in genre.split(',') if g.strip()])
    if runtime:
        tag.setDuration(runtime * 60)  # API gives minutes, Kodi wants seconds


def _tag_tvshow(li, name, year=0, rating=0.0, plot='', cast=None, genre='', director='', runtime=0):
    tag = li.getVideoInfoTag()
    tag.setMediaType('tvshow')
    tag.setTitle(name)
    if year:
        tag.setYear(year)
    if rating:
        tag.setRating(rating)
    if plot:
        tag.setPlot(plot)
    if cast:
        tag.setCast(cast)
    if genre:
        tag.setGenres([g.strip() for g in genre.split(',') if g.strip()])
    if director:
        tag.setDirectors([d.strip() for d in director.split(',') if d.strip()])
    if runtime:
        tag.setDuration(runtime * 60)


def _tag_season(li, title, season_num=0):
    tag = li.getVideoInfoTag()
    tag.setMediaType('season')
    tag.setTitle(title)
    if season_num:
        tag.setSeason(season_num)


def _tag_episode(li, title, series_name='', season_num=0, ep_num=0,
                 plot='', duration=0):
    tag = li.getVideoInfoTag()
    tag.setMediaType('episode')
    tag.setTitle(title)
    if series_name:
        tag.setTvShowTitle(series_name)
    if season_num:
        tag.setSeason(season_num)
    if ep_num:
        tag.setEpisode(ep_num)
    if plot:
        tag.setPlot(plot)
    if duration:
        tag.setDuration(duration)


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------

def list_root(update_listing=False):
    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand')
    # 'addons' suppresses the episode info panel (control 8001 in View_50_List.xml)
    # which shows for 'videos' content and leaves an empty text box below the icon.
    # 'addons' renders the addon icon cleanly in the simple poster panel instead.
    xbmcplugin.setContent(HANDLE, 'addons')

    li = xbmcgui.ListItem(label='Movies', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(HANDLE, build_url(mode='movie_cats'), li, isFolder=True)

    li = xbmcgui.ListItem(label='Series', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(HANDLE, build_url(mode='series_cats'), li, isFolder=True)

    # Wrestling Rewind — single feed URL drives the whole tree.
    # Soft-coded: settings 'wr_root_url' overrides the default if present
    # (see HANDOFF.md re: pointing at a mirror without a code change).
    # Renamed from plain 'Wrestling' in v3.0.0 — three replay sources now
    # sit alongside each other at the root level for honest labelling.
    wr_root = ADDON.getSetting('wr_root_url').strip()
    if not wr_root:
        wr_root = 'https://mylostsoulspace.co.uk/WrestlingRewind/xmls/wrestlingrewind-main.xml'
    li = xbmcgui.ListItem(label='Wrestling Rewind', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode='wr_list', wr_url=wr_root, wr_title='Wrestling Rewind'),
        li, isFolder=True
    )

    # Wrestling on Demand — curated tree from STATIC_MENUS['wod_root'].
    # WWE / Other Promotions / Documentaries / etc.  No live content.
    li = xbmcgui.ListItem(label='Wrestling on Demand', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode='static_menu', key='wod_root', title='Wrestling on Demand'),
        li, isFolder=True
    )

    # Fights on Demand — curated tree from STATIC_MENUS['fod_root'].
    # UFC / MMA / Boxing, including a Free (No Debrid) sub-menu.
    li = xbmcgui.ListItem(label='Fights on Demand', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode='static_menu', key='fod_root', title='Fights on Demand'),
        li, isFolder=True
    )

    # Live — currently single-source (Live Wrestling from WOD's live.xml).
    # Parent menu is in place for future expansion when live fight feeds
    # appear upstream.  See STATIC_MENUS['live_root'].
    li = xbmcgui.ListItem(label='Live', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode='static_menu', key='live_root', title='Live'),
        li, isFolder=True
    )

    # Settings backup / restore — both pinned to the bottom alongside Refresh.
    # SpecialSort=bottom keeps them out of the way; new in v3.0.0 as a safety
    # net for users who fully uninstall + reinstall (which wipes Kodi's
    # per-addon userdata).  Backup writes to special://userdata/, one level
    # above the addon's profile dir, so it survives addon uninstall.
    li = xbmcgui.ListItem(label='Backup Settings', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'fanart': ADDON_FANART})
    li.setProperty('SpecialSort', 'bottom')
    xbmcplugin.addDirectoryItem(
        HANDLE, build_url(mode='settings_backup'), li, isFolder=False
    )

    li = xbmcgui.ListItem(label='Restore Settings', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'fanart': ADDON_FANART})
    li.setProperty('SpecialSort', 'bottom')
    xbmcplugin.addDirectoryItem(
        HANDLE, build_url(mode='settings_restore'), li, isFolder=False
    )

    # Pinned to bottom of the list so it stays out of the way.
    li = xbmcgui.ListItem(label='Refresh / Clear Cache', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'fanart': ADDON_FANART})
    li.setProperty('SpecialSort', 'bottom')
    xbmcplugin.addDirectoryItem(HANDLE, build_url(mode='refresh'), li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE, updateListing=update_listing)


# ---------------------------------------------------------------------------
# Movie views
# ---------------------------------------------------------------------------

def list_movie_categories():
    if not credentials_ok():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    try:
        cats = get_movie_categories()
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading movie categories:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand \u2014 Movies')
    # 'files' instead of 'movies' — tells the skin this is a generic folder list,
    # not a media library view. Aeon Nox Silvo suppresses the right-side info panel
    # for file-browser content, which prevents the genre icons being scaled up.
    xbmcplugin.setContent(HANDLE, 'files')

    for cat in sorted(cats, key=lambda c: c.get('category_name', '').lower()):
        name   = cat.get('category_name', 'Unknown')
        cat_id = str(cat.get('category_id', ''))
        icon   = get_genre_icon(name)
        li = xbmcgui.ListItem(label=name, offscreen=True)
        # 'icon' = small list-row badge. 'thumb' is intentionally the same so the
        # list row renders correctly. Content type 'files' (set above) is what we
        # rely on to suppress the skin's large right-panel info slot — skins treat
        # file-browser views differently from movie/tvshow library views.
        li.setArt({'icon': icon, 'thumb': icon, 'fanart': ADDON_FANART})
        xbmcplugin.addDirectoryItem(
            HANDLE, build_url(mode='movies', cat_id=cat_id, cat_name=name), li, isFolder=True
        )

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def list_movies(cat_id, cat_name=''):
    try:
        movies = get_movies_for_category(cat_id)
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading movies:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    if not movies:
        xbmcgui.Dialog().notification('Echo OnDemand', 'No movies found in this category.', time=3000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(
        HANDLE, 'Echo OnDemand \u2014 {}'.format(cat_name if cat_name else 'Movies')
    )
    xbmcplugin.setContent(HANDLE, 'movies')

    # Always load TMDB cache — it's just a local JSON read, zero API calls.
    # Populated lazily at play time; empty dict if nothing cached yet.
    tmdb_cache = _load_tmdb_cache()

    for m in sorted(movies, key=lambda x: x.get('name', '').lower()):
        name     = m.get('name', 'Unknown').strip()
        vod_id   = str(m.get('stream_id', ''))
        ext      = m.get('container_extension', 'mp4')
        thumb    = m.get('stream_icon', '')
        year     = safe_int(m.get('year', 0))
        rating   = safe_float(m.get('rating', 0))
        plot     = m.get('plot', '')
        cast     = make_cast(m.get('cast', ''))
        director = m.get('director', '')
        genre    = m.get('genre', '')
        runtime  = safe_int(m.get('episode_run_time', 0))
        # Use TMDB backdrop if cached from a previous play; else ADDON_FANART fallback.
        fanart   = tmdb_cache.get(_tmdb_cache_key(name, year), '')

        li = xbmcgui.ListItem(label=name, offscreen=True)
        li.setArt(make_art(thumb=thumb, fanart=fanart))
        _tag_movie(li, name, year=year, rating=rating, plot=plot,
                   cast=cast, director=director, genre=genre, runtime=runtime)
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems(_ctx_movie())

        play_url = build_url(mode='play_movie', vod_id=vod_id, ext=ext,
                             vod_name=name, vod_year=str(year))
        xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.endOfDirectory(HANDLE)


def play_movie(vod_id, ext, vod_name='', vod_year=0):
    """
    Resolve movie stream URL, apply pre-buffer, then fetch and cache TMDB fanart.

    Order is intentional:
      1. setResolvedUrl  — Kodi begins loading the stream immediately.
      2. _apply_buffer   — polls for playback start, pauses, sleeps, resumes.
      3. TMDB fetch      — runs after the buffer ends; the plugin process stays
                           alive after setResolvedUrl so this executes while the
                           stream is already playing. Zero impact on perceived
                           buffer length.
    """
    username, password = get_credentials()
    stream_url = '{}/movie/{}/{}/{}.{}'.format(SERVER, username, password, vod_id, ext)
    log('play_movie: {}'.format(stream_url))
    li = xbmcgui.ListItem(path=stream_url)
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _apply_buffer(get_buffer_secs())
    # TMDB fetch runs after the buffer completes — result cached for future list loads.
    if vod_name and _tmdb_key():
        fetch_and_cache_tmdb_fanart(vod_name, vod_year)


def play_episode(ep_id, ext):
    """Resolve episode stream then apply pre-buffer if configured."""
    username, password = get_credentials()
    stream_url = '{}/series/{}/{}/{}.{}'.format(SERVER, username, password, ep_id, ext)
    log('play_episode: {}'.format(stream_url))
    li = xbmcgui.ListItem(path=stream_url)
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _apply_buffer(get_buffer_secs())


# ---------------------------------------------------------------------------
# Series views
# ---------------------------------------------------------------------------

def list_series_categories():
    if not credentials_ok():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    try:
        cats = get_series_categories()
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading series categories:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand \u2014 Series')
    # Same rationale as movie categories — 'files' to suppress skin info panel.
    xbmcplugin.setContent(HANDLE, 'files')

    for cat in sorted(cats, key=lambda c: c.get('category_name', '').lower()):
        name   = cat.get('category_name', 'Unknown')
        cat_id = str(cat.get('category_id', ''))
        icon   = get_genre_icon(name)
        li = xbmcgui.ListItem(label=name, offscreen=True)
        # Same as movie categories — genre badge in icon slot, Content(files) drives
        # right-panel suppression at the skin level.
        li.setArt({'icon': icon, 'thumb': icon, 'fanart': ADDON_FANART})
        xbmcplugin.addDirectoryItem(
            HANDLE, build_url(mode='series', cat_id=cat_id, cat_name=name), li, isFolder=True
        )

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def list_series(cat_id, cat_name=''):
    try:
        series_list = get_series_for_category(cat_id)
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading series:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    if not series_list:
        xbmcgui.Dialog().notification('Echo OnDemand', 'No series found in this category.', time=3000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(
        HANDLE, 'Echo OnDemand \u2014 {}'.format(cat_name if cat_name else 'Series')
    )
    xbmcplugin.setContent(HANDLE, 'tvshows')

    for s in sorted(series_list, key=lambda x: x.get('name', '').lower()):
        name      = s.get('name', 'Unknown').strip()
        series_id = str(s.get('series_id', ''))
        cover     = s.get('cover', '')
        backdrop  = s.get('backdrop_path', [])
        fanart = (
            backdrop[0] if isinstance(backdrop, list) and backdrop
            else backdrop if isinstance(backdrop, str) else ''
        )
        year     = safe_int(str(s.get('releaseDate', ''))[:4])
        rating   = safe_float(s.get('rating', 0))
        plot     = s.get('plot', '')
        cast     = make_cast(s.get('cast', ''))
        genre    = s.get('genre', '')
        director = s.get('director', '')
        runtime  = safe_int(s.get('episode_run_time', 0))

        li = xbmcgui.ListItem(label=name, offscreen=True)
        li.setArt(make_art(thumb=cover, poster=cover, fanart=fanart))
        _tag_tvshow(li, name, year=year, rating=rating, plot=plot,
                    cast=cast, genre=genre, director=director, runtime=runtime)
        li.addContextMenuItems(_ctx_tvshow())
        xbmcplugin.addDirectoryItem(
            HANDLE, build_url(mode='seasons', series_id=series_id), li, isFolder=True
        )

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.endOfDirectory(HANDLE)


def list_seasons(series_id):
    """
    One folder per season.
    Uses 'seasons' list from API for names/art; falls back to 'episodes' dict keys.
    Series-level backdrop is carried through to every season item so the
    show's fanart stays on screen when the user drills into seasons.
    """
    try:
        info = get_series_info(series_id)
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading series info:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    series_meta = info.get('info', {})
    series_name = series_meta.get('name', 'Unknown')
    episodes    = info.get('episodes', {})
    seasons_api = info.get('seasons', [])

    # Extract series-level fanart so it persists into season and episode views.
    raw_backdrop   = series_meta.get('backdrop_path', [])
    series_fanart  = (
        raw_backdrop[0] if isinstance(raw_backdrop, list) and raw_backdrop
        else raw_backdrop if isinstance(raw_backdrop, str) else ''
    )
    series_cover   = series_meta.get('cover', '')

    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand \u2014 {}'.format(series_name))
    xbmcplugin.setContent(HANDLE, 'seasons')

    season_meta = {}
    for s in seasons_api:
        num = str(s.get('season_number', ''))
        if num:
            season_meta[num] = {
                'name':  s.get('name', 'Season {}'.format(num)),
                'cover': s.get('cover', ''),
            }

    for season_num in sorted(episodes.keys(), key=lambda x: safe_int(x)):
        ep_list = episodes[season_num]
        meta    = season_meta.get(season_num, {})
        label   = meta.get('name') or 'Season {}'.format(season_num)
        # Use season-specific cover if available; fall back to series cover.
        cover   = meta.get('cover', '') or series_cover
        s_int   = safe_int(season_num)

        li = xbmcgui.ListItem(label='{} [{}]'.format(label, len(ep_list)), offscreen=True)
        li.setArt(make_art(thumb=cover, fanart=series_fanart))
        _tag_season(li, label, season_num=s_int)
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url(mode='episodes', series_id=series_id, season=season_num),
            li,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(series_id, season_num):
    """List all episodes for one season. Each item routes through play_episode.
    Series fanart is carried through so the show's backdrop stays visible."""
    try:
        info = get_series_info(series_id)
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading episodes:\n{}'.format(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    series_meta  = info.get('info', {})
    series_name  = series_meta.get('name', 'Unknown')
    episodes     = info.get('episodes', {}).get(str(season_num), [])

    # Series-level fanart — carries through to every episode item.
    raw_backdrop  = series_meta.get('backdrop_path', [])
    series_fanart = (
        raw_backdrop[0] if isinstance(raw_backdrop, list) and raw_backdrop
        else raw_backdrop if isinstance(raw_backdrop, str) else ''
    )

    xbmcplugin.setPluginCategory(
        HANDLE, 'Echo OnDemand \u2014 {} S{}'.format(series_name, season_num)
    )
    xbmcplugin.setContent(HANDLE, 'episodes')

    if not episodes:
        xbmcgui.Dialog().notification('Echo OnDemand', 'No episodes found for this season.', time=3000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    def ep_sort_key(ep):
        return safe_int(ep.get('episode_num', 0))

    for ep in sorted(episodes, key=ep_sort_key):
        ep_id    = str(ep.get('id', ''))
        ext      = ep.get('container_extension', 'mp4')
        ep_num   = safe_int(ep.get('episode_num', 0))
        title    = (ep.get('title') or 'Episode {}'.format(ep_num)).strip()
        label    = '{:02d}. {}'.format(ep_num, title)
        ep_info  = ep.get('info') or {}
        thumb    = ep_info.get('movie_image', '')
        plot     = ep_info.get('plot', '')
        duration = parse_duration(
            ep_info.get('duration_secs') or ep_info.get('duration', 0)
        )

        play_url = build_url(mode='play_episode', ep_id=ep_id, ext=ext)

        li = xbmcgui.ListItem(label=label, offscreen=True)
        # Use episode-specific thumb if available; always use series fanart as backdrop.
        li.setArt(make_art(thumb=thumb, fanart=series_fanart))
        _tag_episode(
            li, title,
            series_name=series_name,
            season_num=safe_int(season_num),
            ep_num=ep_num,
            plot=plot,
            duration=duration,
        )
        li.setProperty('IsPlayable', 'true')
        li.setContentLookup(False)
        li.addContextMenuItems(_ctx_episode())
        xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------------------------------------------------------------------
# MicroJen feed views — Wrestling Rewind, Wrestling on Demand, Fights on Demand
# ---------------------------------------------------------------------------
# All three sources use the same MicroJen XML/JSON format.  list_wr() and
# play_wr() are source-agnostic — they just walk whatever feed URL is handed
# to them.  list_static_menu() handles the curated WOD/FOD category trees
# defined in STATIC_MENUS at the top of this file.
#
# Feed fetching, parsing, and link resolution are delegated to
# resources/lib/wrestling.py (pure data layer).
#
# All views follow the same patterns as the rest of this file: profile-dir
# caching, error dialogs, setContent('files'), _apply_buffer at play time.


def _wr_ttl():
    """MicroJen feed cache TTL — fixed at 30 minutes for all three sources."""
    return 1800


# ---------------------------------------------------------------------------
# Pluto TV HLS header workaround
# ---------------------------------------------------------------------------
# Pluto's edge servers (cfd-v4-service-channel-stitcher-*.prd.pluto.tv) check
# the request's User-Agent and return HTTP 403 for clients that don't look
# like a web browser.  Setting the same browser UA + pluto.tv Referer via
# inputstream.adaptive's header properties as we use for the boot call
# clears that filtering for the actual stream segments too.
#
# This affects WOD's live wrestling channels and Sports Streams — most stream
# from Pluto.  Without these headers, ISA fetches the manifest and gets 403'd
# back ("Download failed, HTTP error 403" from inputstream.adaptive in the
# log).  Non-Pluto HLS streams (e.g., the WWE Network CloudFront feed) work
# without any of this and are left alone.
#
# The User-Agent constant lives in pluto.py and is imported here so both
# the boot session and the playback session present the same client identity.

_PLUTO_HEADERS = urlencode({
    'User-Agent': _pluto.BROWSER_UA,
    'Referer':    'https://pluto.tv/',
}, quote_via=quote)   # %20 for spaces, not '+' — quote is correct for HTTP headers


# Wire pluto.py's diagnostic logging into Kodi's log.  pluto.py uses string
# levels ('INFO', 'WARN', 'ERROR') so it can stay free of Kodi imports;
# we translate to xbmc.LOG* here.  This call runs once at module import time.
def _bridge_pluto_logger(msg, level='INFO'):
    levelmap = {
        'INFO':  xbmc.LOGINFO,
        'WARN':  xbmc.LOGWARNING,
        'ERROR': xbmc.LOGERROR,
    }
    log(msg, levelmap.get(level, xbmc.LOGINFO))

_pluto.set_logger(_bridge_pluto_logger)


def _looks_like_hls(url):
    """True if URL is most likely an HLS stream.

    Looks for the canonical .m3u8 manifest extension anywhere in the URL,
    plus the Pluto TV stitcher path which serves HLS even when the .m3u8
    suffix is buried inside query parameters.
    """
    if not isinstance(url, str):
        return False
    u = url.lower()
    return '.m3u8' in u or 'pluto.tv/stitch/hls/' in u


def _is_pluto_url(url):
    """True if URL is served from Pluto's CDN.  Used to gate header injection
    so we don't ship a fake User-Agent on every HLS request — only the ones
    that need it."""
    return isinstance(url, str) and 'pluto.tv' in url.lower()


def _apply_isa_properties(li, url):
    """Set inputstream.adaptive properties on a ListItem when the URL is HLS.

    No-op when the URL doesn't look like HLS, and the properties are simply
    ignored if inputstream.adaptive isn't installed — so this is safe to
    call unconditionally before setResolvedUrl.

    Why this exists: Kodi's built-in demuxer can fail on session-bound HLS
    streams, particularly Pluto TV's stitcher (which is what backs WOD's
    live wrestling channels — see live.xml).  ISA's HLS handler is more
    forgiving with these.

    Pluto TV detail: Pluto's edge servers reject non-browser clients with
    HTTP 403, so for pluto.tv URLs we also set manifest_headers and
    stream_headers with a Chrome-shaped User-Agent and Referer.  These
    properties are namespaced under inputstream.adaptive and ignored by
    other inputstream addons, so they're scoped correctly.

    Note: as of Kodi 21 (Omega), inputstream.adaptive auto-detects manifest
    type from the response Content-Type / extension.  We previously set
    `inputstream.adaptive.manifest_type=hls` and Kodi logged a deprecation
    warning; that property is now omitted.
    """
    if not _looks_like_hls(url):
        return
    li.setProperty('inputstream', 'inputstream.adaptive')
    if _is_pluto_url(url):
        li.setProperty('inputstream.adaptive.manifest_headers', _PLUTO_HEADERS)
        li.setProperty('inputstream.adaptive.stream_headers',   _PLUTO_HEADERS)


def list_static_menu(menu_key, menu_title):
    """
    Render a hardcoded category tree from STATIC_MENUS.

    Each entry is rendered as either a folder or a playable item:
      * 'wr_url' present     → folder, routes into list_wr against feed XML.
      * 'menu_key' present   → folder, routes into another static menu.
      * 'channel_id' present → playable item, routes to play_pluto with that ID.

    No network I/O, no caching — STATIC_MENUS is plain Python data.

    setContent('files') matches list_wr below; the skin's right-side info
    panel stays suppressed in Aeon Nox Silvo for a uniform look-and-feel.
    """
    entries = STATIC_MENUS.get(menu_key)
    if not entries:
        log('list_static_menu: unknown menu key "{}"'.format(menu_key),
            xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(
            'Echo OnDemand', 'Menu not found.', time=3000
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand \u2014 {}'.format(menu_title))
    xbmcplugin.setContent(HANDLE, 'files')

    for entry in entries:
        title     = entry.get('title', 'Unknown')
        icon_path = _menu_icon(entry.get('icon_label', ''))

        li = xbmcgui.ListItem(label=title, offscreen=True)
        li.setArt({'thumb': icon_path, 'icon': icon_path, 'fanart': ADDON_FANART})

        if 'wr_url' in entry:
            # Leaf — drills into list_wr against the feed XML.
            target_url = build_url(
                mode='wr_list', wr_url=entry['wr_url'], wr_title=title
            )
            is_folder = True
        elif 'menu_key' in entry:
            # Branch — drills into another static menu.
            target_url = build_url(
                mode='static_menu', key=entry['menu_key'], title=title
            )
            is_folder = True
        elif 'channel_id' in entry:
            # Playable Pluto channel — resolved at play time via pluto.py.
            li.setProperty('IsPlayable', 'true')
            target_url = build_url(
                mode='play_pluto', channel_id=entry['channel_id'], title=title
            )
            is_folder = False
        else:
            # Malformed entry — skip rather than break the whole listing.
            log('list_static_menu: entry "{}" has none of wr_url / menu_key / channel_id'
                .format(title), xbmc.LOGWARNING)
            continue

        xbmcplugin.addDirectoryItem(HANDLE, target_url, li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def list_wr(wr_url, wr_title='Wrestling Rewind'):
    """
    Fetch and display one level of a MicroJen feed (Wrestling Rewind, WOD, FOD).

    Folders (type=dir) route back to list_wr with the sub-feed URL.
    Playable items (type=item) route to play_wr with the item encoded as
    base64 JSON — handles list-typed link fields (sublinks) cleanly in a
    single URL parameter.

    v2.6.0 enhancements vs 2.5.0:
      - item-type entries with empty links are now skipped (previously listed
        but unplayable on click)
      - dir-type entries with list-typed links use the first list element
        (was urlencoding the list into a broken navigation URL)
      - item-level thumbnail/fanart used when present (was always ADDON_ICON)
      - title format tags stripped for clean display (handles WOD/FOD BBCode)
      - Plot infotag set when item has a summary (Info popup works; right
        panel suppression unchanged because it depends on setContent('files'))
    """
    profile = _profile_dir()
    ttl     = _wr_ttl()

    text = _wr.cache_load(profile, wr_url, ttl)
    if text is None:
        try:
            text = _wr.fetch_feed(wr_url)
            _wr.cache_save(profile, wr_url, text)
        except Exception as e:
            xbmcgui.Dialog().ok(
                'Echo OnDemand', 'Error loading feed:\n{}'.format(e)
            )
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    items = _wr.parse_feed(wr_url, text)

    if not items:
        xbmcgui.Dialog().notification(
            'Echo OnDemand', 'No items found in this section.', time=3000
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Echo OnDemand \u2014 {}'.format(wr_title))
    xbmcplugin.setContent(HANDLE, 'files')

    for item in items:
        item_type = item.get('type', 'item')
        raw_title = item.get('title', 'Unknown')
        # Strip BBCode-style format tags ([COLOR ...], [B], [I], etc.) that
        # WOD / FOD sometimes embed.  Wrestling Rewind titles pass through
        # unchanged because they don't use these tags.
        title     = _wr.strip_format_tags(raw_title) or 'Unknown'
        raw_link  = item.get('link', '')

        # Skip ANY entry with an empty link — for dir items they'd navigate
        # to a broken URL, for item-type they'd hit "No playable link" on click.
        if not raw_link:
            log('list_wr: skipping {} "{}" — empty link'.format(
                item_type, title), xbmc.LOGWARNING)
            continue

        # Pick item-level art when present, addon defaults otherwise.
        thumb_url  = (item.get('thumbnail') or '').strip() or ADDON_ICON
        fanart_url = (item.get('fanart')    or '').strip() or ADDON_FANART
        summary    = (item.get('summary')   or '').strip()

        li = xbmcgui.ListItem(label=title, offscreen=True)
        li.setArt({'thumb': thumb_url, 'icon': thumb_url, 'fanart': fanart_url})

        if item_type == 'dir':
            # A dir's link is normally a single feed-XML URL.  If the parser
            # produced a list (rare but possible per the schema), take the
            # first element rather than letting urlencode mangle the list.
            dir_link = raw_link[0] if isinstance(raw_link, list) and raw_link else raw_link
            if not isinstance(dir_link, str) or not dir_link:
                log('list_wr: dir "{}" has unusable link, skipping'.format(title),
                    xbmc.LOGWARNING)
                continue
            target_url = build_url(mode='wr_list', wr_url=dir_link, wr_title=title)
            xbmcplugin.addDirectoryItem(HANDLE, target_url, li, isFolder=True)
        else:
            # Playable item.  If a summary is present, expose it through
            # InfoTagVideo so pressing Info shows context.  setContent('files')
            # is unchanged so Aeon Nox Silvo still suppresses the right panel.
            if summary:
                tag = li.getVideoInfoTag()
                tag.setMediaType('video')
                tag.setTitle(title)
                tag.setPlot(summary)

            payload = {
                'title': title,
                'link':  raw_link,
            }
            encoded = base64.urlsafe_b64encode(
                json.dumps(payload).encode('utf-8')
            ).decode('utf-8')
            li.setProperty('IsPlayable', 'true')
            target_url = build_url(mode='wr_play', wr_item=encoded)
            xbmcplugin.addDirectoryItem(HANDLE, target_url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def _pluto_resolver_enabled():
    """Read the kill-switch setting.  Default true.  Returns False only
    when the user has explicitly turned the resolver off in settings."""
    val = (ADDON.getSetting('pluto_resolver_enabled') or 'true').strip().lower()
    return val not in ('false', '0', 'no', 'off')


def _maybe_resolve_pluto(url, title=''):
    """If url is a Pluto stitcher URL and the resolver is enabled, replace
    it with a freshly-minted URL from boot.pluto.tv.  On any failure (resolver
    disabled, no channel ID, network error, channel not in boot response)
    return the original URL unchanged so we never make things worse than
    v3.0.2.  Logs which path was taken so the Kodi log shows whether the
    resolver fired or not."""
    if not _is_pluto_url(url):
        return url
    if not _pluto_resolver_enabled():
        log('play: Pluto resolver disabled by setting, using original URL', xbmc.LOGINFO)
        return url

    channel_id = _pluto.extract_channel_id(url)
    if not channel_id:
        log('play: Pluto URL but no channel ID extracted: {}'.format(url[:80]),
            xbmc.LOGWARNING)
        return url

    fresh = _pluto.get_fresh_url(channel_id)
    if not fresh:
        log('play: Pluto resolver returned no URL for channel {} — falling back'
            .format(channel_id), xbmc.LOGWARNING)
        return url

    log('play: Pluto channel {} resolved to fresh URL ("{}")'
        .format(channel_id, title), xbmc.LOGINFO)
    return fresh


def play_wr(wr_item):
    """
    Resolve and play a Wrestling item.

    Resolution order (handled by wrestling.resolve_best_link):
      1. Try resolveurl on each candidate — debrid wins if available.
      2. Fall back to any direct video URL.
      3. Fall back to the first HTTP URL and let Kodi try it.

    For Pluto TV URLs, an extra step runs after wrestling.resolve_best_link
    — we mint a fresh stitcher URL via pluto.py.  This sidesteps the stale
    session token problem in WOD's live.xml.  Falls back silently to the
    original URL on any resolver failure.

    Pre-buffer applied using same setting and mechanism as IPTV playback.
    """
    try:
        item = json.loads(base64.urlsafe_b64decode(wr_item))
    except Exception as e:
        log('play_wr: failed to decode item: {}'.format(e), xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    title    = item.get('title', '')
    raw_link = item.get('link', '')

    links = _wr.normalise_links(raw_link)
    if not links:
        log('play_wr: no usable links in item "{}"'.format(title), xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('Echo OnDemand', 'No playable link found.', time=3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    url, via_debrid = _wr.resolve_best_link(links)

    if not url:
        xbmcgui.Dialog().notification('Echo OnDemand', 'Could not resolve stream.', time=3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # For Pluto URLs, swap in a freshly-minted URL from boot.pluto.tv.
    # Silent passthrough for non-Pluto URLs (e.g., WWE Network CloudFront).
    url = _maybe_resolve_pluto(url, title)

    log('play_wr: "{}" -> {} (debrid={})'.format(title, url[:60], via_debrid))

    li = xbmcgui.ListItem(path=url)
    li.setContentLookup(False)
    # If the resolved URL is HLS (Pluto TV live channels, .m3u8 manifests),
    # hand it to inputstream.adaptive — Kodi's built-in demuxer can fail on
    # session-bound HLS.  No-op for direct mp4/mkv/etc. and harmless if ISA
    # isn't installed.
    _apply_isa_properties(li, url)

    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _apply_buffer(get_buffer_secs())


def play_pluto(channel_id, title=''):
    """
    Resolve and play a Pluto TV channel directly by its channel ID.

    Used by Sports Streams entries (STATIC_MENUS['live_sports']) — the user
    picked a specific channel from a curated list, so we go straight to the
    Pluto resolver without needing to walk a feed first.

    Failure mode: if the resolver returns no URL (network error, channel not
    in the boot response, region-locked away from this user), show a brief
    notification and bail.  No fallback URL exists for play_pluto entries —
    the channel ID IS the only address we have, unlike play_wr where a
    stitcher URL is also baked into the feed.
    """
    if not channel_id:
        log('play_pluto: empty channel_id', xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    if not _pluto_resolver_enabled():
        xbmcgui.Dialog().notification(
            'Echo OnDemand',
            'Pluto resolver is disabled in settings.',
            time=3000
        )
        log('play_pluto: resolver disabled, cannot play channel {}'.format(channel_id),
            xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    url = _pluto.get_fresh_url(channel_id)
    if not url:
        xbmcgui.Dialog().notification(
            'Echo OnDemand',
            'Could not resolve channel.\nMay be region-locked or retired.',
            time=4000
        )
        log('play_pluto: no URL for channel {} ("{}")'.format(channel_id, title),
            xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    log('play_pluto: channel {} ("{}") -> {}'.format(channel_id, title, url[:60]))

    li = xbmcgui.ListItem(path=url)
    li.setContentLookup(False)
    _apply_isa_properties(li, url)

    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _apply_buffer(get_buffer_secs())


# ---------------------------------------------------------------------------
# Settings backup / restore
# ---------------------------------------------------------------------------
# Kodi normally preserves settings across addon upgrades — when you "Install
# from zip" over an existing addon, userdata/addon_data/<addon_id>/settings.xml
# is left alone.  But if a user fully uninstalls and then reinstalls (a common
# workflow for hobbyist users sideloading zips), Kodi wipes that directory.
#
# Backup/Restore writes a JSON snapshot one level up — to special://userdata/
# itself — which survives any single-addon uninstall.  The file lives at:
#     special://userdata/echoondemand_settings.json
#
# Format:
#     {
#         "version":  1,
#         "ts":       <unix timestamp>,
#         "settings": { "<setting_id>": "<value>", ... }
#     }
#
# Currently captures all four user-facing settings: username, password,
# buffer_secs, tmdb_api_key.  Adding settings later is a one-line edit to
# _BACKUP_KEYS below.

_BACKUP_KEYS = ('username', 'password', 'buffer_secs', 'tmdb_api_key')
_BACKUP_VERSION = 1


def _backup_path():
    """Path to the settings backup JSON, outside the addon's own userdata dir."""
    base = xbmcvfs.translatePath('special://userdata/')
    if isinstance(base, bytes):
        base = base.decode('utf-8')
    return os.path.join(base, 'echoondemand_settings.json')


def do_settings_backup():
    """Snapshot all _BACKUP_KEYS settings to the user-level userdata directory."""
    snapshot = {
        'version':  _BACKUP_VERSION,
        'ts':       time.time(),
        'settings': {k: ADDON.getSetting(k) for k in _BACKUP_KEYS},
    }
    path = _backup_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
        log('Settings backup written to {}'.format(path), xbmc.LOGINFO)
        xbmcgui.Dialog().notification(
            'Echo OnDemand', 'Settings backed up.', time=2500
        )
    except Exception as e:
        log('Settings backup FAILED: {}'.format(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            'Echo OnDemand',
            'Could not write settings backup:\n{}'.format(e)
        )


def do_settings_restore():
    """Read the backup snapshot and write each value back via ADDON.setSetting."""
    path = _backup_path()
    if not os.path.exists(path):
        xbmcgui.Dialog().ok(
            'Echo OnDemand',
            'No backup found at:\n{}\n\nUse "Backup Settings" first.'.format(path)
        )
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
    except Exception as e:
        log('Settings restore: read failed: {}'.format(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            'Echo OnDemand',
            'Backup file unreadable:\n{}'.format(e)
        )
        return

    # Version guard — if the snapshot was written by a future Echo OnDemand
    # with an incompatible schema, refuse rather than silently corrupting.
    snap_version = safe_int(snapshot.get('version', 0))
    if snap_version > _BACKUP_VERSION:
        xbmcgui.Dialog().ok(
            'Echo OnDemand',
            'Backup is from a newer addon version ({}) than this one ({}).\n'
            'Refusing to restore.'.format(snap_version, _BACKUP_VERSION)
        )
        return

    settings = snapshot.get('settings', {})
    if not isinstance(settings, dict):
        xbmcgui.Dialog().ok(
            'Echo OnDemand', 'Backup file is malformed (settings field).'
        )
        return

    # Confirm before overwriting current values — one click of the wrong menu
    # entry shouldn't silently replace a working configuration.
    confirmed = xbmcgui.Dialog().yesno(
        'Echo OnDemand',
        'Restore settings from backup?\n'
        'Current Settings will be overwritten.',
        nolabel='Cancel', yeslabel='Restore'
    )
    if not confirmed:
        return

    restored = 0
    for key in _BACKUP_KEYS:
        if key in settings:
            try:
                ADDON.setSetting(key, str(settings[key] or ''))
                restored += 1
            except Exception as e:
                log('Settings restore: failed to set {}: {}'.format(key, e),
                    xbmc.LOGWARNING)
    log('Settings restore: {} keys applied from {}'.format(restored, path),
        xbmc.LOGINFO)
    xbmcgui.Dialog().notification(
        'Echo OnDemand',
        'Restored {} setting{}.'.format(restored, '' if restored == 1 else 's'),
        time=2500
    )


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

def do_refresh():
    cache_clear_all()
    xbmcgui.Dialog().notification('Echo OnDemand', 'Cache cleared.', time=2000)
    list_root(update_listing=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def router(paramstring):
    params    = dict(parse_qsl(paramstring.lstrip('?')))
    mode      = params.get('mode')
    cat_id    = params.get('cat_id', '')
    cat_name  = params.get('cat_name', '')
    series_id = params.get('series_id', '')
    season    = params.get('season', '')
    vod_id    = params.get('vod_id', '')
    ep_id     = params.get('ep_id', '')
    ext       = params.get('ext', 'mp4')
    vod_name  = params.get('vod_name', '')
    vod_year  = safe_int(params.get('vod_year', 0))
    wr_url    = params.get('wr_url', '')
    wr_title  = params.get('wr_title', 'Wrestling Rewind')
    wr_item   = params.get('wr_item', '')
    # Static menu params (WOD/FOD curated trees + Live sub-menus).
    menu_key   = params.get('key', '')
    menu_title = params.get('title', '')
    # Pluto TV channel-by-ID playback (Sports Streams).
    channel_id = params.get('channel_id', '')

    if mode == 'movie_cats':
        list_movie_categories()
    elif mode == 'movies':
        list_movies(cat_id, cat_name)
    elif mode == 'play_movie':
        play_movie(vod_id, ext, vod_name, vod_year)
    elif mode == 'play_episode':
        play_episode(ep_id, ext)
    elif mode == 'series_cats':
        list_series_categories()
    elif mode == 'series':
        list_series(cat_id, cat_name)
    elif mode == 'seasons':
        list_seasons(series_id)
    elif mode == 'episodes':
        list_episodes(series_id, season)
    elif mode == 'wr_list':
        list_wr(wr_url, wr_title)
    elif mode == 'wr_play':
        play_wr(wr_item)
    elif mode == 'static_menu':
        list_static_menu(menu_key, menu_title)
    elif mode == 'play_pluto':
        play_pluto(channel_id, menu_title)
    elif mode == 'settings_backup':
        do_settings_backup()
    elif mode == 'settings_restore':
        do_settings_restore()
    elif mode == 'refresh':
        do_refresh()
    else:
        list_root()


if __name__ == '__main__':
    router(sys.argv[2])
