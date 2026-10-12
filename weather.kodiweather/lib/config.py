import xbmc
import xbmcvfs
import xbmcaddon

from . import utils

# Static tables (API templates, property maps, WMO / fanart codes) live in maps.py; fanart helpers in fanart.py.
# Re-exported here so the rest of the add-on keeps using config.<name>.
from .maps import *  # noqa: F401,F403
from .fanart import get_fanart_folder, safe_fanart_code, get_fanartbg  # noqa: F401

# Limits
# NOTE: maxdays is a module-level global because it's read by api.py, utils.py,
# and weather.py via `config.maxdays`. The import-time value below is a safe
# fallback that's used only for the brief window before config.init() runs.
# config.init() -> addon() refreshes maxdays so a settings change actually
# takes effect without needing a Kodi restart.
try:
	maxdays = utils.setting('fcdays', 'int')
	if maxdays < 3:
		maxdays = 8  # Fallback if setting is missing, zero, or corrupt
except (ValueError, TypeError):
	maxdays = 8  # Fallback default if setting not available at import
mindays  = 1
# Hourly detail kept as window properties: Silvo's hourly page reads Hourly.1 to Hourly.17 and the old custom window 1 to 24,
# so 24 hours ahead and no past hours are enough (was 72 ahead and 23 back = ~4x the properties for nothing).
maxhours = 24
minhours = 1
mindata  = 0
maxdata  = 300

# Radar: refresh every 10 minutes (the service wakes every 5), keep at most 8 frames (each is a 768x768 RGBA texture in the
# window), and start over with a full download when the newest frame is more than 45 minutes old.
radarrefresh = 600
radarframes  = 8
radargap     = 2700

# ADDON
addon_ua    = {'user-agent': f'{xbmc.getUserAgent()} (weather.kodiweather v{utils.xbmcaddon.Addon().getAddonInfo("version")})'}
addon_info  = f'{xbmc.getUserAgent()} (weather.kodiweather v{utils.xbmcaddon.Addon().getAddonInfo("version")})'
addon_data  = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
addon_cache = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile')) + "cache"
addon_icons = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path')) + "resources/icons"
addon_path  = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path'))
neterr      = 0

# Cache
dnscache = {}
mapcache = {}

# Modules (disabled)
# sys.path.append(f'{addon_path}/lib/modules')

# Dynamic localization mapping
def localization():

	localization.wmo = {
		'0d': utils.locaddon(32200),
		'0n': utils.locaddon(32250),
		'1d': utils.locaddon(32201),
		'1n': utils.locaddon(32251),
		'2d': utils.locaddon(32202),
		'2n': utils.locaddon(32202),
		'3d': utils.locaddon(32203),
		'3n': utils.locaddon(32203),
		'45d': utils.locaddon(32204),
		'45n': utils.locaddon(32204),
		'48d': utils.locaddon(32205),
		'48n': utils.locaddon(32205),
		'51d': utils.locaddon(32206),
		'51n': utils.locaddon(32206),
		'53d': utils.locaddon(32207),
		'53n': utils.locaddon(32207),
		'55d': utils.locaddon(32208),
		'55n': utils.locaddon(32208),
		'56d': utils.locaddon(32209),
		'56n': utils.locaddon(32209),
		'57d': utils.locaddon(32210),
		'57n': utils.locaddon(32210),
		'61d': utils.locaddon(32211),
		'61n': utils.locaddon(32211),
		'63d': utils.locaddon(32212),
		'63n': utils.locaddon(32212),
		'65d': utils.locaddon(32213),
		'65n': utils.locaddon(32213),
		'66d': utils.locaddon(32214),
		'66n': utils.locaddon(32214),
		'67d': utils.locaddon(32215),
		'67n': utils.locaddon(32215),
		'71d': utils.locaddon(32216),
		'71n': utils.locaddon(32216),
		'73d': utils.locaddon(32217),
		'73n': utils.locaddon(32217),
		'75d': utils.locaddon(32218),
		'75n': utils.locaddon(32218),
		'77d': utils.locaddon(32219),
		'77n': utils.locaddon(32219),
		'80d': utils.locaddon(32220),
		'80n': utils.locaddon(32220),
		'81d': utils.locaddon(32221),
		'81n': utils.locaddon(32221),
		'82d': utils.locaddon(32222),
		'82n': utils.locaddon(32222),
		'85d': utils.locaddon(32223),
		'85n': utils.locaddon(32223),
		'86d': utils.locaddon(32224),
		'86n': utils.locaddon(32224),
		'95d': utils.locaddon(32225),
		'95n': utils.locaddon(32225),
		'96d': utils.locaddon(32226),
		'96n': utils.locaddon(32226),
		'99d': utils.locaddon(32227),
		'99n': utils.locaddon(32227)
	}

	localization.weekday = {
		'1': utils.loc(11),
		'2': utils.loc(12),
		'3': utils.loc(13),
		'4': utils.loc(14),
		'5': utils.loc(15),
		'6': utils.loc(16),
		'7': utils.loc(17)
	}

	localization.weekdayshort = {
		'1': utils.loc(41),
		'2': utils.loc(42),
		'3': utils.loc(43),
		'4': utils.loc(44),
		'5': utils.loc(45),
		'6': utils.loc(46),
		'7': utils.loc(47)
	}

	localization.timeofday = {
		0: utils.locaddon(32480),
		1: utils.locaddon(32481),
		2: utils.locaddon(32482),
		3: utils.locaddon(32483),
	}

	localization.layers = {
		'iemradar': utils.locaddon(32400),
	}

# Alert thresholds
# One row per measurement: (graph key, type, unit, icon, localised name id, threshold kinds)
# kinds: h = high_1..3, l = low_1..3, w = wmo_1..3 (condition codes). The user's thresholds live in settings as
# alert_<type>_<high|low|wmo>_<1..3>; alert() reads them into alert.map in this row order.
ALERT_SPEC = [
	( 'temperature.graph'               , 'temperature'             , 'temperature'   , 'temperature'   , 32320, 'hl' ),
	( 'precipitation.graph'             , 'precipitation'           , 'precipitation' , 'precipitation' , 32321, 'h' ),
	( 'snow.graph'                      , 'snow'                    , 'snow'          , 'snow'          , 32217, 'h' ),
	( 'condition.graph'                 , 'condition'               , ''              , 'condition'     , 32322, 'w' ),
	( 'windspeed.graph'                 , 'windspeed'               , 'speed'         , 'wind'          , 32323, 'h' ),
	( 'windgust.graph'                  , 'windgust'                , 'speed'         , 'wind'          , 32324, 'h' ),
	( 'feelslike.graph'                 , 'feelslike'               , 'temperature'   , 'temperature'   , 32332, 'hl' ),
	( 'dewpoint.graph'                  , 'dewpoint'                , 'temperature'   , 'temperature'   , 32333, 'hl' ),
	( 'cloudiness.graph'                , 'cloudiness'              , '%'             , 'cloud'         , 32334, 'h' ),
	( 'humidity.graph'                  , 'humidity'                , '%'             , 'humidity'      , 32346, 'h' ),
	( 'precipitationprobability.graph'  , 'precipitationprobability', '%'             , 'precipitation' , 32321, 'h' ),
	( 'pressure.graph'                  , 'pressure'                , 'pressure'      , 'pressure'      , 32347, 'hl' ),
	( 'pressuresurface.graph'           , 'pressuresurface'         , 'pressure'      , 'pressure'      , 32347, 'hl' ),
	( 'solarradiation.graph'            , 'solarradiation'          , 'solarradiation', 'solarradiation', 32348, 'h' ),
	( 'visibility.graph'                , 'visibility'              , 'distance'      , 'visibility'    , 32349, 'l' ),
	( 'uvindex.graph'                   , 'uvindex'                 , 'uvindex'       , 'uvindex'       , 32329, 'h' ),
	( 'aqius.graph'                     , 'aqius'                   , 'index'         , 'health'        , 32326, 'h' ),
	( 'pm25.graph'                      , 'pm25'                    , 'particles'     , 'particles'     , 32327, 'h' ),
	( 'pm10.graph'                      , 'pm10'                    , 'particles'     , 'particles'     , 32328, 'h' ),
	( 'co.graph'                        , 'co'                      , 'particles'     , 'particles'     , 32337, 'h' ),
	( 'ozone.graph'                     , 'ozone'                   , 'particles'     , 'particles'     , 32338, 'h' ),
	( 'dust.graph'                      , 'dust'                    , 'particles'     , 'particles'     , 32339, 'h' ),
	( 'no2.graph'                       , 'no2'                     , 'particles'     , 'particles'     , 32330, 'h' ),
	( 'so2.graph'                       , 'so2'                     , 'particles'     , 'particles'     , 32331, 'h' ),
]
_ALERT_KIND = { 'h': 'high', 'l': 'low', 'w': 'wmo' }

def alert(cache=False):
	alert.map = {}

	for key, type, unit, icon, loc, kinds in ALERT_SPEC:
		entry = { 'type': type, 'unit': unit, 'icon': icon, 'loc': loc }

		for kind in kinds:
			name = _ALERT_KIND[kind]

			for n in (1, 2, 3):
				setting = f'alert_{type}_{name}_{n}'
				entry[setting] = utils.setting(setting, 'str', cache)

		alert.map[key] = entry

def addon(cache=False):

	# Vars
	addon.settings   = utils.settings()
	addon.alerts     = 0
	addon.msgqueue   = []

	# Bool
	addon.debug       = utils.setting('debug', 'bool', cache)
	addon.verbose     = utils.setting('verbose', 'bool', cache)
	addon.enablehour  = utils.setting('enablehour', 'bool', cache)
	addon.enablegraphs = utils.setting('enablegraphs', 'bool', cache)

	# Str
	addon.unitsep     = utils.setting('unitsep', 'str', cache)
	addon.temp        = utils.setting('unittemp', 'str', cache)     or 'app'
	addon.tempdp      = utils.setting('unittempdp', 'str', cache)   or '1'
	addon.speed       = utils.setting('unitspeed', 'str', cache)    or 'mph'
	addon.speeddp     = utils.setting('unitspeeddp', 'str', cache)  or '1'
	addon.precip      = utils.setting('unitprecip', 'str', cache)   or 'in'
	addon.precipdp    = utils.setting('unitprecipdp', 'str', cache)  or '1'
	addon.snow        = utils.setting('unitsnow', 'str', cache)      or 'in'
	addon.snowdp      = utils.setting('unitsnowdp', 'str', cache)    or '1'
	addon.distance    = utils.setting('unitdistance', 'str', cache)  or 'mi'
	addon.distancedp  = utils.setting('unitdistancedp', 'str', cache) or '1'
	addon.particlesdp = utils.setting('unitparticlesdp', 'str', cache) or '1'
	addon.pollendp    = utils.setting('unitpollendp', 'str', cache)  or '1'
	addon.uvindexdp   = utils.setting('unituvindexdp', 'str', cache) or '1'
	addon.pressure    = utils.setting('unitpressure', 'str', cache)  or 'inHg'
	addon.pressuredp  = utils.setting('unitpressuredp', 'str', cache) or '0'
	addon.radiationdp = utils.setting('unitradiationdp', 'str', cache) or '1'
	addon.cdefault    = utils.setting('colordefault', 'str', cache)
	addon.cnegative   = utils.setting('colornegative', 'str', cache)
	addon.cnormal     = utils.setting('colornormal', 'str', cache)
	addon.cnotice     = utils.setting('colornotice', 'str', cache)
	addon.ccaution    = utils.setting('colorcaution', 'str', cache)
	addon.cdanger     = utils.setting('colordanger', 'str', cache)

	# Int
	addon.mapzoom     = utils.setting('mapzoom', 'int', cache)
	addon.maphistory  = utils.setting('maphistory', 'int', cache)
	addon.alerthours  = max(1, utils.setting('alert_hours', 'int', cache))
	addon.fcstart     = utils.setting('fcstart', 'int', cache)
	addon.fcend       = utils.setting('fcend', 'int', cache)

	# Map settings
	addon.mapprovider = utils.setting('mapprovider', 'str', cache) or 'osm'

	# Maxlocs
	if utils.setting('explocations', 'bool', cache):
		addon.maxlocs = 6
	else:
		addon.maxlocs = 4

	# Refresh module-level maxdays so a settings change to 'fcdays' takes
	# effect on the next service tick instead of requiring a Kodi restart.
	# Read via config.maxdays in api.py, utils.py, and weather.py.
	global maxdays
	try:
		new_maxdays = utils.setting('fcdays', 'int', cache)
		if new_maxdays < 3:
			new_maxdays = 8
	except (ValueError, TypeError):
		new_maxdays = 8
	maxdays = new_maxdays

def kodi():
	kodi.long     = utils.region('datelong')
	kodi.date     = utils.region('dateshort')
	kodi.time     = utils.region('time')
	kodi.meri     = utils.region('meridiem')
	kodi.speed    = utils.region('speedunit')
	kodi.temp     = utils.region('tempunit')
	kodi.height   = 1080

def loc(locid, cache=False):
	loc.prop = {}
	loc.id   = locid
	loc.cid  = str(utils.settingrpc("weather.currentlocation") or 1)
	loc.lat  = utils.setting(f'loc{locid}lat', 'float')
	loc.lon  = utils.setting(f'loc{locid}lon', 'float')
	loc.utz  = utils.setting(f'loc{locid}utz', 'bool')

	# Name
	name = utils.setting(f'loc{locid}', 'str')
	user = utils.setting(f'loc{locid}user', 'str')

	if user:
		loc.name  = user
		loc.short = user
	else:
		loc.name  = name
		loc.short = name.split(',')[0]

	# Timezone
	try:
		loc.tz = utils.timezone(utils.setting(f'loc{locid}tz'))
	except (KeyError, ValueError):
		loc.tz = utils.timezone('UTC')

def init(cache=False):
	kodi()
	localization()
	addon(cache)
	alert(cache)

	# Directory
	utils.createdir()

