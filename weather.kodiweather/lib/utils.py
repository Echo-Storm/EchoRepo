import xbmc
import xbmcgui
import xbmcaddon
import math
import json
import time
import xml.etree.ElementTree as ET

from datetime import datetime
from pytz import timezone
from pathlib import Path

from . import config
from . import conv
from . import weather
from . import monitor

# Monitor
monitor = monitor.Main()

# Logging
def log(msg, level=0):
	if level == 1:
		xbmc.log(msg=f'[weather.kodiweather]: [W] {msg}', level=xbmc.LOGINFO)
	elif level == 2:
		xbmc.log(msg=f'[weather.kodiweather]: [E] {msg}', level=xbmc.LOGINFO)
	elif level == 3:
		if config.addon.debug:
			xbmc.log(msg=f'[weather.kodiweather]: [D] {msg}', level=xbmc.LOGINFO)
	elif level == 4:
		if config.addon.verbose:
			xbmc.log(msg=f'[weather.kodiweather]: [V] {msg}', level=xbmc.LOGINFO)
	else:
		xbmc.log(msg=f'[weather.kodiweather]: [I] {msg}', level=xbmc.LOGINFO)

# Setting
def setting(arg, type='str', cache=False):

	# Cache
	if cache:
		try:
			value = config.addon.settings[arg]
		except (KeyError, AttributeError):
			value = xbmcaddon.Addon().getSetting(arg)
	else:
		value = xbmcaddon.Addon().getSetting(arg)

	# Type
	if type == 'int':
		try:
			return int(value)
		except (ValueError, TypeError):
			return 0

	elif type == 'float':
		try:
			return float(value)
		except (ValueError, TypeError):
			return 0.0

	elif type == 'bool':

		if value == 'true':
			return True
		else:
			return False

	else:
		return str(value)

def setsetting(arg, value):
	xbmcaddon.Addon().setSetting(arg, str(value))

def settingrpc(setting):
	try:
		r = json.loads(xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"Settings.GetSettingValue", "params": {{"setting": "{}"}} }}'.format(setting)))
	except (ValueError, TypeError):
		return None
	else:
		# an error reply has no 'result': give None instead of raising AttributeError
		return (r.get('result') or {}).get('value')

def settings(changed=False):
	dict = {}
	skip = [ 'alert_notification', 'service', 'geoip' ]
	file = Path(config.addon_data + 'settings.xml')

	try:
		with open(file, 'r', encoding='utf-8') as f:
			data = f.read()

		root = ET.fromstring(data)
	except (OSError, ET.ParseError, UnicodeDecodeError):
		return dict
	else:
		for item in root:
			id = item.attrib['id']

			if changed:
				if not 'loc' in id and not id in skip:
					dict[id] = item.text
			else:
				dict[id] = item.text

		return dict

def region(arg):
	return xbmc.getRegion(arg)

# Geolocation
def geoip(create=False):
	f = Path(f'{config.addon_data}/geoip')

	if create:
		with open(f, mode='w'):
			pass
	else:
		return f.is_file()

# Localization
def loc(arg):
	return xbmc.getLocalizedString(arg)

def locaddon(arg):
	return xbmcaddon.Addon().getLocalizedString(arg)

# Notification
def notification(header, msg, icon, locid):
	log(f'[LOC{locid}] Notification: {header} - {msg}')

	# Floor at 3 seconds so a corrupt or missing alert_duration setting (which
	# our guarded setting() returns as 0) can't pass a non-positive duration
	# to xbmcgui. Same floor that weather.py:notification uses.
	seconds  = max(3, setting('alert_duration', 'int'))
	duration = (seconds - 2) * 1000
	xbmcgui.Dialog().notification(header, msg, icon, int(duration))

# Datetime
def dt(arg, stamp=0):

	if arg == 'stamputc':
		return datetime.fromtimestamp(int(stamp), tz=timezone('UTC'))
	elif arg == 'stamploc':
		if config.loc.utz:
			return datetime.fromtimestamp(int(stamp), tz=timezone('UTC')).astimezone(config.loc.tz)
		else:
			return datetime.fromtimestamp(int(stamp), tz=timezone('UTC')).astimezone()
	elif arg == 'nowutc':
		return datetime.now(tz=timezone('UTC'))
	elif arg == 'nowutcstamp':
		return int(datetime.now(tz=timezone('UTC')).timestamp())
	elif arg == 'nowloc':
		if config.loc.utz:
			return datetime.now(tz=timezone('UTC')).astimezone(config.loc.tz)
		else:
			return datetime.now(tz=timezone('UTC')).astimezone()
	elif arg == 'isoutc':
		return datetime.fromisoformat(stamp)
	elif arg == 'isoloc':
		if config.loc.utz:
			return datetime.fromisoformat(stamp).astimezone(config.loc.tz)
		else:
			return datetime.fromisoformat(stamp).astimezone()
	elif arg == 'dayofyear':
		return datetime.today().timetuple().tm_yday

# Convert ISO 8601 datetime string to localised display string (for NWS alert expiry)
def conv_isodt(isostr):
	try:
		dt_obj = datetime.fromisoformat(isostr).astimezone()
		return dt_obj.strftime(f'{config.kodi.date} {config.kodi.time}')
	except Exception:
		return isostr

# Last update
def lastupdate(arg):
	try:
		time1 = setting(arg)
		time2 = dt('nowutcstamp')
		return int(time2) - int(time1)
	except (ValueError, TypeError):
		return 321318000

def setupdate(arg):
	setsetting(arg, dt('nowutcstamp'))

# Window property

def winprop(property):
	return xbmcgui.Window(12600).getProperty(property)

# Set Window property
def setprop(property, data, window=12600):
	xbmcgui.Window(window).setProperty(property, str(data))

# Set properties
def setprops():
	for i in sorted(config.loc.prop):
		setprop(i, config.loc.prop[i])

# Add property
def addprop(property, content):
	config.loc.prop[property] = content

# Window property (Get)
def getprop(data, map, idx, count):

	# Content
	if len(map[1]) == 1:
		if idx is not None:
			content = data[map[1][0]][idx]
		else:
			content = data[map[1][0]]
	elif len(map[1]) == 2:
		if idx is not None:
			content = data[map[1][0]][map[1][1]][idx]
		else:
			content = data[map[1][0]][map[1][1]]
	elif len(map[1]) == 3:
		if idx is not None:
			content = data[map[1][0]][map[1][1]][map[1][2]][idx]
		else:
			content = data[map[1][0]][map[1][1]][map[1][2]]
	else:
		# Defensive fallthrough: previously this left `content` unbound and
		# raised UnboundLocalError two lines below. setmap's TypeError handler
		# catches this and logs a clean message instead of crashing the update.
		raise TypeError(f'Unsupported map[1] key path length {len(map[1])}: {map[1]!r}')

	if content is None:
		raise TypeError('No data')

	# Unit
	unit = map[3]

	# WMO (isday)
	if unit.startswith('wmo') or unit == 'image' or unit == 'code':
		if idx is not None:
			try:
				if data[map[1][0]]['is_day'][idx] == 1:
					isday = 'd'
				else:
					isday = 'n'
			except (KeyError, IndexError, TypeError):
				isday = 'd'
		else:
			try:
				if data[map[1][0]]['is_day'] == 1:
					isday = 'd'
				else:
					isday = 'n'
			except (KeyError, IndexError, TypeError):
				isday = 'd'

	# Tools
	if unit == 'round':
		content = int(round(content))
	elif unit == 'roundpercent':
		content = f'{int(round(content))}%'
	elif unit == 'round2':
		content = round(content, 2)
	elif unit == 'wmocond':
		content = config.localization.wmo.get(f'{content}{isday}')
	elif unit == 'image':
		# KODI workaround for DayX.OutlookIcon, add "resource://resource.images.weathericons.default" to path
		if map[2][0] == 'day':
			content = f'resource://resource.images.weathericons.default/{config.map_wmo.get(f"{content}{isday}")}.png'
		else:
			# Non-day targets (current.outlookicon, hourly.X.outlookicon etc.) produce a
			# bare "34.png"-style value.  The skin home screen uses this as a fanart folder
			# name (stripping .png), so it must carry the REDIRECTED folder number — the
			# same value that fanartcode carries — otherwise the skin requests non-existent
			# consolidated folders (e.g. resources/34/ when only resources/32/ exists).
			kodi_code = config.map_wmo.get(f'{content}{isday}')
			content = f'{config.get_fanart_folder(kodi_code) if kodi_code is not None else kodi_code}.png'
	elif unit == 'code':
		kodi_code = config.map_wmo.get(f'{content}{isday}')
		if kodi_code is None:
			raise TypeError(f'No map_wmo entry for WMO code {content!r} isday={isday!r}')
		content = config.get_fanart_folder(kodi_code)
		if content is None:
			raise TypeError(f'No map_fanart entry for kodi_code {kodi_code}')
	elif unit == 'date':
		content = dt('stamploc', content).strftime(config.kodi.date)
	elif unit == 'time':
		content = conv.time('time', content)
	elif unit == 'timeiso':
		content = conv.time('timeiso', content)
	elif unit == 'hour':
		content = conv.time('hour', content)
	elif unit == 'seconds':
		m, s = divmod(int(content), 60)
		h, m = divmod(m, 60)
		content = f'{h:d}:{m:02d}'
	elif unit == 'weekday':
		content = config.localization.weekday.get(dt('stamploc', content).strftime('%u'))
	elif unit == 'weekdayshort':
		content = config.localization.weekdayshort.get(dt('stamploc', content).strftime('%u'))
	elif unit == '%':
		content = f'{content}%'

	# Temperature
	elif unit == 'temperature':
		content = conv.temp(content)
	elif unit == 'temperaturekodi':
		content = conv.temp(content, True)
	elif unit == 'temperatureunit':
		content = f'{conv.temp(content)}{conv.temp()}'
	elif unit == 'unittemperature':
		content = conv.temp()

	# Speed
	elif unit == 'speed':
		content = conv.speed(content)
	elif unit == 'unitspeed':
		content = conv.speed()
	elif unit == 'speedunit':
		content = f'{conv.speed(content)} {conv.speed()}'

	# Precipitation
	elif unit == 'precipitation':
		content = conv.precip(content)
	elif unit == 'unitprecipitation':
		content = conv.precip()

	# Snow
	elif unit == 'snow':
		content = conv.snow(content)
	elif unit == 'unitsnow':
		content = conv.snow()

	# Distance
	elif unit == 'distance':
		content = conv.distance(content)
	elif unit == 'unitdistance':
		content = conv.distance()

	# UVIndex
	elif unit == 'uvindex':
		content = conv.dp(content, config.addon.uvindexdp)

	# Particles
	elif unit == 'particles':
		content = conv.dp(content, config.addon.particlesdp)
	elif unit == 'unitparticles':
		content = 'μg/m³'

	# Pollen
	elif unit == 'pollen':
		content = conv.dp(content, config.addon.pollendp)
	elif unit == 'unitpollen':
		content = f'{locaddon(32456)}/m³'

	# Radiation
	elif unit == 'radiation':
		content = conv.dp(content, config.addon.radiationdp)
	elif unit == 'unitradiation':
		content = 'W/m²'

	# Pressure
	elif unit == 'pressure':
		content = conv.pressure(content)
	elif unit == 'unitpressure':
		content = conv.pressure()

	# Direction
	elif unit == 'direction':
		content = conv.direction(content)

	# Percent
	elif unit == 'unitpercent':
		content = '%'

	# Wind
	elif unit == 'windkodi':
		speed     = round(conv.speed(data['current']['wind_speed_10m']), True)
		unit      = conv.speed(False, True)
		direction = conv.direction(data['current']['wind_direction_10m'])
		content   = loc(434).format(direction, int(speed), unit)

	# Moonphase
	elif unit == 'moonphase':
		content = conv.moonphase(int(content))

	elif unit == 'moonphaseimage':
		content = f'{config.addon_icons}/moon/{conv.moonphaseimage(int(content))}'

	# Season
	elif unit == 'season':
		content = conv.season(float(content))

	# Graphs (graphs.py)
	elif unit == 'graph':
		from . import graphs
		return graphs.build(data, map)

	# TimeOfDay (timeofday.py)
	elif unit == 'timeofday':
		from . import timeofday
		return timeofday.build(data, map)

	# Return data
	return content

# Get file
def getfile(file):
	try:
		# Note: Changing language throws an exception without enforcing utf8
		with open(Path(f'{config.addon_cache}/{file}'), 'r', encoding='utf8') as f:
			data = json.load(f)

	except Exception as e:
		log(f'{e}', 2)
		return None

	else:
		return data

# Index
def index(arg, data):
	if arg == 'now':
		match = dt('nowloc').strftime('%Y-%m-%d %H')
	elif arg == 'mid':
		match = dt('nowloc').strftime('%Y-%m-%d 00')
	elif arg == 'day':
		match = dt('nowloc').strftime('%Y-%m-%d')

	for idx in range(config.mindata, config.maxdata):

		try:
			if arg == 'day':
				timecheck = dt('stamploc', data['daily']['time'][idx]).strftime('%Y-%m-%d')
			else:
				timecheck = dt('stamploc', data['hourly']['time'][idx]).strftime('%Y-%m-%d %H')
		except (KeyError, IndexError, TypeError, ValueError):
			return None
		else:
			if timecheck == match:
				return idx

# Directory
def createdir():
	p = Path(config.addon_data)
	p.mkdir(parents=True, exist_ok=True)

# LatLon2Coords
def lat2coords(lat_deg, lon_deg, zoom):
	lat_rad = math.radians(lat_deg)
	n = 1 << zoom
	xtile = int((lon_deg + 180.0) / 360.0 * n)
	ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
	return xtile, ytile

def numTiles(z):
	return(pow(2,z))

def latEdges(y,z):
	n = numTiles(z)
	unit = 1 / n
	relY1 = y * unit
	relY2 = relY1 + unit
	lat1 = mercatorToLat(math.pi * (1 - 2 * relY1))
	lat2 = mercatorToLat(math.pi * (1 - 2 * relY2))
	return(lat1,lat2)

def lonEdges(x,z):
	n = numTiles(z)
	unit = 360 / n
	lon1 = -180 + x * unit
	lon2 = lon1 + unit
	return(lon1,lon2)

def mercatorToLat(mercatorY):
	return(math.degrees(math.atan(math.sinh(mercatorY))))

def coords2bbox(x,y,z):
	lat1,lat2 = latEdges(y,z)
	lon1,lon2 = lonEdges(x,z)
	return((lat2, lon1, lat1, lon2)) # S,W,N,E

