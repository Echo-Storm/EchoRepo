#!/usr/bin/env python3
"""
plugin.video.echoondemand — Echo OnDemand  v2.2.0
Kodi Omega (v21) plugin for browsing and playing VOD content (Movies and Series)
from an Xtream Codes IPTV service, plus Wrestling Rewind replays via debrid.

Changes in 2.2.0 (wrestling parser audit):
  - _collect_items(): wrapper detection is now generic — any intermediate
    XML element is tried as a wrapper, not just <xml>.  Previous code silently
    returned [] for feeds (e.g. PPV) that use a different wrapper element name.
  - parse_feed(): mutual XML/JSON fallback.  If primary parser returns empty
    and content looks like the other format, the other parser is tried.
    Handles feeds where URL extension does not match actual content type.
  - parse_feed(): LOGINFO diagnostic emitted when both parsers return empty —
    visible in the Kodi log without debug mode.
  - resolve_best_link(): all three passes (debrid, direct, fallback) now log
    at LOGINFO so debrid activity is always visible without debug mode.
  - resolve_best_link(): _url_from_resolved() handles both plain string and
    ResolvedURL object returns from newer resolveurl builds.  Also embeds
    any headers from ResolvedURL in Kodi's native pipe format.

Changes in 2.1.1 (sublink nesting fix):
  - Added Wrestling Rewind section to root menu.
  - resources/lib/wrestling.py: pure data layer — fetch, parse, resolve.
    Handles MicroJen XML and JSON feed formats with 3-pass XML recovery.
  - list_wr(): navigates WR XML/JSON directory feeds, same caching pattern
    as the rest of the addon.
  - play_wr(): debrid-first resolution via resolveurl, silent direct-link
    fallback.  No link chooser dialog — seamless like the rest of the addon.
  - Pre-buffer applied to WR playback using the same setting as IPTV.
  - addon.xml: script.module.resolveurl added as required dependency.
  - settings.xml: wr_root_url (overridable feed URL) + wr_cache_ttl.
  - Routing: wr_list, wr_play modes added.

Changes in 2.0.0 (final polish pass):
  - list_root: setContent changed from 'videos' to 'addons'. 'videos' triggered
    the skin's episode info panel (control 8001) which rendered the addon icon at
    the top and left an empty text box below it. 'addons' uses the simple poster
    panel instead — clean icon display, no dead space.
  - Removed unused URLError import (api_get docstring is the documentation; all
    callers use except Exception which already catches it).
  - Stale 'icons restored' comment removed from list_series_categories.
  - Companion skin edits (MyVideoNav.xml, View_50_List.xml):
      * Plot synopsis overlay restricted to movies + tvshows — removed from
        episodes where the skin already provides a full right-side info panel.
      * Genre category right-panel suppressed in VideoList and SlimVideoList via
        Container.Content(files) + Container.PluginName condition.
      * InfoPanel overlay (views 52-59) also suppressed for category views.
      * Duplicate IsCollection label removed from VideoList movies itemlayout.
      * Ghost control 4421 reference removed from MyVideoNav.xml.

Changes in 1.3.1 (audit + cosmetic fixes):
  - credentials_ok() now guarded in list_movie_categories/list_series_categories
    so deep links (favourites, skin widgets) show a proper "configure credentials"
    dialog instead of a raw API error.
  - cat_name threaded through URL params; list_movies/list_series now call
    setPluginCategory with the actual genre name for correct breadcrumb display.
  - list_series: added empty-list guard (notification + endOfDirectory succeeded=False)
    to match list_movies behaviour.
  - list_episodes: added empty-episode-list guard for the same reason.
  - list_seasons: setContent changed from 'tvshows' to 'seasons' (correct Kodi type).
  - Refresh item: isFolder changed False→True (was misusing the playable-item contract).
  - play_movie: TMDB fetch moved to after _apply_buffer so it truly runs while the
    stream is already playing, not before the buffer cycle starts.
  - _apply_buffer docstring: removed stale "show notification toast" step.
  - Category list items use Content('files') to drive right-panel suppression at
    the skin level rather than manipulating art keys.

Routing:
  (root)                                    -> list_root()
  mode=movie_cats                                   -> list_movie_categories()
  mode=movies       cat_id=X  cat_name=Y            -> list_movies(cat_id, cat_name)
  mode=series_cats                                  -> list_series_categories()
  mode=series       cat_id=X  cat_name=Y            -> list_series(cat_id, cat_name)
  mode=seasons      series_id=X                     -> list_seasons(series_id)
  mode=episodes     series_id=X  season=N           -> list_episodes(series_id, season_num)
  mode=play_movie   vod_id=X     ext=Y              -> play_movie(vod_id, ext)
  mode=wr_list      wr_url=X    [wr_title=Y]        -> list_wr(wr_url, wr_title)
  mode=wr_play      wr_item=X                       -> play_wr(wr_item)
  mode=refresh                                      -> clear all cache, go to root

Cache strategy (all files live in addon profile dir):
  movie_cats.json          TTL 1 hour   -- list of movie genre categories
  series_cats.json         TTL 1 hour   -- list of series genre categories
  movies_{cat_id}.json     TTL 30 min   -- movie list for one category
  series_{cat_id}.json     TTL 30 min   -- series list for one category
  seriesinfo_{id}.json     TTL 1 hour   -- full season/episode data for one series

Stream URL formats (standard Xtream Codes):
  Movie:   {server}/movie/{user}/{pass}/{vod_id}.{ext}
  Episode: {server}/series/{user}/{pass}/{episode_id}.{ext}

Assumptions:
  - Service is Xtream Codes-compatible (player_api.php supported).
  - Extension (.mkv, .mp4, etc.) comes from the API field 'container_extension'.
  - All artwork URLs come from the API. Nothing is generated locally.
  - Kodi Omega (v21) / Python 3.
"""

import sys
import json
import os
import time
import glob
from urllib.parse import parse_qsl, urlencode
from urllib.request import urlopen, Request

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from resources.lib import wrestling as _wr

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
    pattern = os.path.join(_profile_dir(), '*.json')
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            log('Deleted cache: {}'.format(os.path.basename(path)))
        except Exception as e:
            log('Could not delete {}: {}'.format(path, e), xbmc.LOGWARNING)


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
    if not credentials_ok():
        return

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

    wr_root = ADDON.getSetting('wr_root_url').strip()
    if not wr_root:
        wr_root = 'https://mylostsoulspace.co.uk/WrestlingRewind/xmls/wrestlingrewind-main.xml'
    li = xbmcgui.ListItem(label='Wrestling Rewind', offscreen=True)
    li.setArt({'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'fanart': ADDON_FANART})
    xbmcplugin.addDirectoryItem(
        HANDLE, build_url(mode='wr_list', wr_url=wr_root, wr_title='Wrestling Rewind'),
        li, isFolder=True
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
        return
    try:
        cats = get_movie_categories()
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading movie categories:\n{}'.format(e))
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
        return
    try:
        cats = get_series_categories()
    except Exception as e:
        xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading series categories:\n{}'.format(e))
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
# Wrestling Rewind views
# ---------------------------------------------------------------------------
# These functions handle navigation of MicroJen XML/JSON feeds from the
# Wrestling Rewind service.  All feed fetching, parsing, and link resolution
# is delegated to resources/lib/wrestling.py (pure data layer).
#
# list_wr() and play_wr() follow exactly the same patterns as the rest of
# this file: profile-dir caching, error dialogs, setContent, _apply_buffer.


def _wr_ttl():
    """Read WR cache TTL from settings. Returns seconds. Default 30 minutes."""
    try:
        return max(60, int(float(ADDON.getSetting('wr_cache_ttl') or '30')) * 60)
    except (ValueError, TypeError):
        return 1800


def list_wr(wr_url, wr_title='Wrestling Rewind'):
    """
    Fetch and display one level of a Wrestling Rewind MicroJen feed.

    Folders (type=dir) route back to list_wr with the sub-feed URL.
    Playable items (type=item) route to play_wr with the item encoded as
    base64 JSON — same pattern used internally by Wrestling Rewind itself,
    kept here because it handles lists of sublinks cleanly in a single URL
    parameter without per-field encoding gymnastics.
    """
    import base64

    profile = _profile_dir()
    ttl     = _wr_ttl()

    # Fetch (or serve from cache)
    text = _wr.cache_load(profile, wr_url, ttl)
    if text is None:
        try:
            text = _wr.fetch_feed(wr_url)
            _wr.cache_save(profile, wr_url, text)
        except Exception as e:
            xbmcgui.Dialog().ok('Echo OnDemand', 'Error loading Wrestling Rewind:\n{}'.format(e))
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
    # 'videos' is appropriate for wrestling replays — generic video list,
    # no library metadata panels, no season/episode structure expected.
    xbmcplugin.setContent(HANDLE, 'videos')

    for item in items:
        item_type = item.get('type', 'item')
        title     = item.get('title', 'Unknown').strip()
        thumbnail = item.get('thumbnail') or ADDON_ICON
        fanart    = item.get('fanart')    or ADDON_FANART
        summary   = item.get('summary', '')
        raw_link  = item.get('link', '')

        li = xbmcgui.ListItem(label=title, offscreen=True)
        li.setArt({'thumb': thumbnail, 'icon': thumbnail, 'fanart': fanart})

        if title or summary:
            tag = li.getVideoInfoTag()
            tag.setMediaType('video')
            if title:
                tag.setTitle(title)
            if summary:
                tag.setPlot(summary)

        if item_type == 'dir':
            # Directory — navigate into the sub-feed.
            # wr_title carries the folder label through for setPluginCategory.
            target_url = build_url(mode='wr_list', wr_url=raw_link, wr_title=title)
            xbmcplugin.addDirectoryItem(HANDLE, target_url, li, isFolder=True)
        else:
            # Playable item.  Encode the full item dict as base64 JSON so that
            # play_wr receives all fields (including list-typed link fields from
            # sublinks) in a single URL-safe parameter.
            payload = {
                'title':     title,
                'link':      raw_link,   # may be str or list
                'thumbnail': thumbnail,
                'summary':   summary,
            }
            encoded = base64.urlsafe_b64encode(
                json.dumps(payload).encode('utf-8')
            ).decode('utf-8')

            li.setProperty('IsPlayable', 'true')
            target_url = build_url(mode='wr_play', wr_item=encoded)
            xbmcplugin.addDirectoryItem(HANDLE, target_url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def play_wr(wr_item):
    """
    Resolve and play a Wrestling Rewind item.

    Resolution order (handled by wrestling.resolve_best_link):
      1. Try resolveurl on each candidate URL — debrid wins if available.
      2. Fall back to any direct video URL.
      3. Fall back to the first HTTP URL and let Kodi try it.

    Pre-buffer is applied using the same setting and mechanism as IPTV
    movie/episode playback — consistent behaviour across all content types.
    """
    import base64

    try:
        item    = json.loads(base64.urlsafe_b64decode(wr_item))
    except Exception as e:
        log('play_wr: failed to decode item: {}'.format(e), xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    title     = item.get('title', '')
    raw_link  = item.get('link', '')
    thumbnail = item.get('thumbnail', '') or ADDON_ICON

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

    log('play_wr: "{}" -> {} (debrid={})'.format(title, url[:60], via_debrid))

    li = xbmcgui.ListItem(path=url)
    li.setContentLookup(False)
    if title:
        tag = li.getVideoInfoTag()
        tag.setMediaType('video')
        tag.setTitle(title)
    if thumbnail:
        li.setArt({'thumb': thumbnail, 'icon': thumbnail})

    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _apply_buffer(get_buffer_secs())


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
    elif mode == 'refresh':
        do_refresh()
    else:
        list_root()


if __name__ == '__main__':
    router(sys.argv[2])
