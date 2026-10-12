"""Weather fanart folder redirects and the stable home-screen background picker.

config.py re-exports get_fanart_folder, safe_fanart_code and get_fanartbg.
"""
import random
import xbmcvfs

from . import utils
from .maps import map_fanart, map_wmo

def get_fanart_folder(code):
	"""Return the fanart folder for a given Yahoo weather code.
	   Redirects clone codes to their master folder.
	   Returns None if code is None (caller should treat as no-data)."""
	if code is None:
		return None
	return map_fanart.get(code, code)

def safe_fanart_code(wmo_code, isday):
	"""Convenience wrapper: WMO int + isday char -> fanart folder int.

	Returns None (not a string) if either map lookup fails so the caller can
	decide what fallback to use (typically '' for a Kodi window property).
	This replaces the scattered inline pattern
	  config.get_fanart_folder(config.map_wmo.get(f'{code}{isday}'))
	which silently propagated None through both dicts and ended up setting
	the Kodi property to the string 'None', causing skin lookup errors.
	"""
	kodi_code = map_wmo.get(f'{wmo_code}{isday}')
	if kodi_code is None:
		return None
	return map_fanart.get(kodi_code, kodi_code)

# Fanart background - stable image selection
# Keyed by str(locid). Holds {'code': str, 'path': str} per location.
# Persists for the lifetime of the Kodi session so the same image is shown
# until the weather code or day/night state actually changes.
_fanartbg_state = {}

def get_fanartbg(code, locid):
	"""Return a stable full image path for the given fanart code and location.

	Three-level fallback chain so the home-screen background almost never goes
	black, even when the per-code folder is missing/empty or `code` itself is
	empty (which happens briefly when weather.json is partial or weather_code
	comes back null from Open-Meteo):

	  1. Real per-code folder under resources/{code}/  — cached, stable.
	  2. Previously-cached real image when called with an empty code — preserves
	     the last good background instead of degrading to a Fallback.
	  3. resources/Fallback_*.jpg — cached with a `fallback` flag so the next
	     tick re-tries the real folder and recovers automatically.
	  4. '' — only if the resource pack itself is unreadable (very rare).

	Returns a special:// path or '' if absolutely nothing is available.
	"""
	key      = str(locid)
	# Treat None and '' the same — both mean "no usable code this tick".
	code_str = '' if code in (None, '') else str(code)
	entry    = _fanartbg_state.get(key, {})

	# Cache hit on a real (non-Fallback) image for the same code — keep it.
	if not entry.get('fallback') and entry.get('code') == code_str and entry.get('path') and code_str:
		return entry['path']

	# Empty code: prefer the last known-good real image over a Fallback.
	# This handles the "fanartcode briefly missing" failure mode without
	# flickering away from a perfectly fine background.
	if not code_str and not entry.get('fallback') and entry.get('path'):
		return entry['path']

	# Try the per-code folder.
	if code_str:
		try:
			folder_uri = f'special://home/addons/resource.images.weatherfanart.echo/resources/{code_str}/'
			_, files   = xbmcvfs.listdir(folder_uri)
			imgs       = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
			if imgs:
				chosen = random.choice(imgs)
				path   = f'{folder_uri}{chosen}'
				_fanartbg_state[key] = {'code': code_str, 'path': path, 'fallback': False}
				utils.log(f'[LOC{locid}] fanartbg: code={code_str} -> {chosen}', 3)
				return path
		except Exception as e:
			utils.log(f'[LOC{locid}] fanartbg: per-code listdir failed for {code_str!r}: {e}', 3)

	# Per-code lookup failed (or code was empty). If we already picked a
	# Fallback in this state, keep it stable instead of flicking between
	# different Fallbacks on every service tick.
	if entry.get('fallback') and entry.get('path'):
		return entry['path']

	# Final fallback: random Fallback_*.jpg from resources/.
	try:
		root_uri  = 'special://home/addons/resource.images.weatherfanart.echo/resources/'
		_, files  = xbmcvfs.listdir(root_uri)
		fallbacks = [f for f in files
		             if f.lower().startswith('fallback_')
		             and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
		if fallbacks:
			chosen = random.choice(fallbacks)
			path   = f'{root_uri}{chosen}'
			# Cache with fallback flag so the cache check at top doesn't
			# treat this as a "real" hit, but the stability check above does.
			_fanartbg_state[key] = {'code': code_str, 'path': path, 'fallback': True}
			utils.log(f'[LOC{locid}] fanartbg: using Fallback {chosen} (code={code_str!r})', 3)
			return path
	except Exception as e:
		utils.log(f'[LOC{locid}] fanartbg: Fallback listdir failed: {e}', 3)

	utils.log(f'[LOC{locid}] fanartbg: no image available (code={code_str!r}); returning empty', 2)
	return ''

