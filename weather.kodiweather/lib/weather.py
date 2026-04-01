import os
import xbmc

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from . import config
from . import utils
from . import conv

class Main():

	### MAIN
	def __init__(self, locid, mode='kodi'):

		if utils.monitor.abortRequested():
			return

		# Import API only when needed
		if mode == 'download' or mode == 'geoip' or locid.startswith('loc'):
			global api
			from . import api

		# GeoIP
		if mode == 'geoip':
			api.getloc(locid)
			return

		# Search
		if locid.startswith('loc'):
			api.setloc(locid[3])
			return

		# Init
		self.init(locid, mode)

		if not config.loc.lat or not config.loc.lon:
			utils.log(f'[LOC{locid}] Not configured', 1)
			return

		# Download
		if self.mode == 'download':

			# Weather - also re-download if cache file missing
			if utils.lastupdate(f'loc{locid}data') >= 3600 or not Path(f'{config.addon_cache}/{locid}/weather.json').exists():
				with ThreadPoolExecutor(3) as pool:
					pool.map(self.getdata, config.map)

				if api.network():
					utils.setupdate(f'loc{locid}data')

			# Map - also re-download if cache file missing
			if utils.lastupdate(f'loc{locid}map') >= 604800 or not Path(f'{config.addon_cache}/{locid}/osm.png').exists():
				self.getmap('osm')

				if api.network():
					utils.setupdate(f'loc{locid}map')

			# Rv - also re-download if cache folder missing
			if utils.lastupdate(f'loc{locid}rv') >= 3600 or not Path(f'{config.addon_cache}/{locid}/iemradar').exists():
				self.getmap('iemradar')

				if api.network():
					utils.setupdate(f'loc{locid}rv')

			# NWS Alerts - also re-download if cache file missing
			if utils.setting('noaalerts_enabled', 'bool') and (utils.lastupdate(f'loc{locid}noaalerts') >= 3600 or not Path(f'{config.addon_cache}/{locid}/noaalerts.json').exists()):
				api.getnoaalerts(locid, config.loc.lat, config.loc.lon)

				if api.network():
					utils.setupdate(f'loc{locid}noaalerts')

		# Update
		elif self.mode == 'update' or self.mode == 'kodi':

			# Wait for service thread
			if self.mode == 'kodi':
				utils.monitor.waitForService()

			# KODI
			for map in config.map:
				self.setdata(map)

			self.setother()
			self.setnwsalerts()
			utils.setprops()

		# Update locs
		elif self.mode == 'updatelocs':

			# KODI
			self.setlocs()
			utils.setprops()

		# Notification (Queue)
		elif self.mode == 'msgqueue':
			for map in config.map:
				self.msgqueue(map)
			self.nwsalertqueue()

		# Notification (Send)
		elif self.mode == 'msgsend':
			self.notification()

	### INIT
	def init(self, locid, mode):

		if mode == 'download':
			utils.log(f'[LOC{locid}] Initialising: mode={mode}, neterr={config.neterr}, net={api.network()}, dnscache={len(config.dnscache)}', 3)
		else:
			utils.log(f'[LOC{locid}] Initialising: mode={mode}', 3)

		# Location
		config.loc(locid)

		# Vars
		self.mode     = mode
		self.data     = {}
		self.today    = utils.dt('nowloc').strftime('%Y-%m-%d')

		# Directory
		p = Path(f'{config.addon_cache}/{locid}')
		p.mkdir(parents=True, exist_ok=True)

	### GET DATA
	def getdata(self, type):
		utils.log(f'[LOC{config.loc.id}] Downloading data: {type}', 3)
		api.getdata(type, config.loc.id, [ config.loc.lat, config.loc.lon, self.today ])

	### SET DATA
	def setdata(self, type):

		# Data
		self.data[type] = utils.getfile(f'{config.loc.id}/{type}.json')
		if not self.data[type]:
			utils.log(f'No {type} data for location {config.loc.id}', 2)
			return

		# Index
		indexnow = utils.index("now", self.data[type])
		indexmid = utils.index("mid", self.data[type])
		indexday = utils.index("day", self.data[type])

		# Update data
		utils.log(f'[LOC{config.loc.id}] Updating data: {type}', 3)

		for map in config.map.get(type):

			# Current (Compatibility)
			if map[0] == 'current':
				self.setmap(type, map)

			# Current (KODI)
			elif map[0] == 'currentkodi' and self.mode == 'kodi':
				self.setmap(type, map)

			# Hourly (Compatibility)
			elif map[0] == 'hourly':
				self.setmulti(type, [ map, 'hourly', indexnow, config.maxhours, config.minhours, 'hourly' ])

				if config.addon.enablehour:
					self.setmulti(type, [ map, 'hourly', indexmid, config.maxhours, config.minhours, 'hour' ])

			# Daily (Compatibility)
			elif map[0] == 'daily':
				self.setmulti(type, [ map, 'daily', indexday, config.maxdays, config.mindays, 'daily' ])
				self.setmulti(type, [ map, 'daily', indexday, config.maxdays, config.mindays, 'day' ])

			# Daily (KODI)
			elif map[0] == 'dailykodi' and self.mode == 'kodi':
				self.setmulti(type, [ map, 'daily', indexday, config.maxdays, config.mindays, 'daily' ])
				self.setmulti(type, [ map, 'daily', indexday, config.maxdays, config.mindays, 'day' ])

			# TimeOfDay
			elif map[0] == 'timeofday':
				self.setmap(type, map)

			# Graph
			elif map[0] == 'graph':
				self.setmap(type, map)

			# Alert
			if map[3] == 'graph':
				self.setalert(type, [ map, indexnow ])

	### SET CURRENT
	def setcurrent(self, type, locid):

		# Data
		self.data[type] = utils.getfile(f'{locid}/{type}.json')
		if not self.data[type]:
			utils.log(f'No {type} data for location {locid}', 2)
			return

		# Update data
		utils.log(f'[LOC{locid}] Updating current: {type}', 3)

		for map in config.map.get(type):

			# Current (Compatibility)
			if map[0] == 'current':
				self.setmap(type, map, locid=locid)

	### SET LOCATIONS
	def setlocs(self):
		locs = 0
		for locid in range(1, config.addon.maxlocs):
			loc     = utils.setting(f'loc{locid}')
			locuser = utils.setting(f'loc{locid}user')

			if loc:
				locs += 1

				# Set "Current.X" only if called from service
				if self.mode != 'kodi':
					for map in config.map:
						self.setcurrent(map, locid)

				if locuser:
					utils.addprop(f'location{locid}', locuser)
				else:
					utils.addprop(f'location{locid}', loc)
			else:
				utils.addprop(f'location{locid}', '')

		utils.addprop('locations', locs)

	## SET ALERT
	def setalert(self, src, map):
		winprops = [ 'name', 'value', 'icon', 'unit', 'time', 'hours', 'status' ]

		data   = self.data[src]
		type   = map[0][2][1]
		idx    = map[1]
		prop   = config.alert.map[type]['type']
		unit   = config.alert.map[type]['unit']
		icon   = config.alert.map[type]['icon']
		name   = utils.locaddon(config.alert.map[type]['loc'])
		hours  = 0
		code   = 0
		value  = 0

		# Invalid index
		if not idx:
			utils.log('Index invalid, weather data is not up to date ...', 3)
			return

		# Alert disabled
		if not utils.setting(f'alert_{prop}_enabled', 'bool', True):
			utils.log(f'Disabled alert: {prop}', 3)

			utils.addprop(f'alert.{prop}', '')
			for winprop in winprops:
				utils.addprop(f'alert.{prop}.{winprop}', '')

			return

		# Checking alert
		utils.log(f'Checking alert: {prop}', 3)
		l  = []
		ll = []

		for index in range(idx, idx + config.addon.alerthours):

			try:
				v  = int(data[map[0][1][0]][map[0][1][1]][index])
				vv = int(data[map[0][1][0]]['time'][index])
			except:
				if not self.mode == 'msgqueue':
					utils.addprop(f'alert.{prop}', 0)
					for winprop in winprops:
						utils.addprop(f'alert.{prop}.{winprop}', '')
				return
			else:
				l.append(v)
				ll.append(vv)

		for c, d in [(x, y) for x in [ 3, 2, 1 ] for y in [ 'high', 'low', 'wmo' ] ]:
			alert = f'alert_{prop}_{d}_{c}'
			last  = False

			try:
				if d == 'wmo':
					limit = list(config.alert.map[type][alert].split(' '))
				else:
					limit = int(config.alert.map[type][alert])
			except:
				continue

			for idx, v in enumerate(l):

				if d == 'high':
					if v >= limit:
						hours += 1
						if last and v > last:
							code, value, last, stamp = c, v, v, ll[idx]
						elif not last:
							code, value, last, stamp = c, v, v, ll[idx]
				elif d == 'low':
					if v <= limit:
						hours += 1
						if last and v < last:
							code, value, last, stamp = c, v, v, ll[idx]
						elif not last:
							code, value, last, stamp = c, v, v, ll[idx]
				elif d == 'wmo':
					for wmo in limit:
						if v == int(wmo):
							hours += 1
							if last and v > last:
								code, value, last, stamp = c, v, v, ll[idx]
							elif not last:
								code, value, last, stamp = c, v, v, ll[idx]
			if hours:
				break

		# Check alert code
		if code != 0:
			icon = f'{icon}{code}'
			time  = conv.time('time', stamp)

			if prop == 'condition':
				icon  = f'{config.map_alert_condition.get(value)}{code}'
				value = config.localization.wmo.get(f'{value}d')
			else:
				value, unit = conv.item(value, unit)

			# Notification Queue
			if self.mode == 'msgqueue':
				if code == 1 and utils.setting(f'alert_{prop}_notice', 'bool'):
					config.addon.msgqueue.append([ f'{config.loc.short} - {utils.locaddon(32340)} ({hours} {utils.locaddon(32288)})', f'({time}) {name}: {value}{unit}', f'{config.addon_icons}/alert/{icon}.png' ])
				elif code == 2 and utils.setting(f'alert_{prop}_caution', 'bool'):
					config.addon.msgqueue.append([ f'{config.loc.short} - {utils.locaddon(32341)} ({hours} {utils.locaddon(32288)})', f'({time}) {name}: {value}{unit}', f'{config.addon_icons}/alert/{icon}.png' ])
				elif code == 3 and utils.setting(f'alert_{prop}_danger', 'bool'):
					config.addon.msgqueue.append([ f'{config.loc.short} - {utils.locaddon(32342)} ({hours} {utils.locaddon(32288)})', f'({time}) {name}: {value}{unit}', f'{config.addon_icons}/alert/{icon}.png' ])

				return

			# Set alert properties
			utils.log(f'Updating alert: {prop} = {code}', 3)
			config.addon.alerts += 1

			utils.addprop(f'alert.{prop}', code)
			utils.addprop(f'alert.{prop}.name', name)
			utils.addprop(f'alert.{prop}.time', time)
			utils.addprop(f'alert.{prop}.hours', hours)
			utils.addprop(f'alert.{prop}.icon', f'{config.addon_icons}/alert/{icon}.png')
			utils.addprop(f'alert.{prop}.value', value)
			utils.addprop(f'alert.{prop}.unit', unit)

			if code == 1:
				utils.addprop(f'alert.{prop}.status', utils.locaddon(32340))
			elif code == 2:
				utils.addprop(f'alert.{prop}.status', utils.locaddon(32341))
			elif code == 3:
				utils.addprop(f'alert.{prop}.status', utils.locaddon(32342))

		else:
			if self.mode == 'msgqueue':
				return

			utils.addprop(f'alert.{prop}', 0)
			for winprop in winprops:
				utils.addprop(f'alert.{prop}.{winprop}', '')

	### SET QUEUE
	def msgqueue(self, type):

		# Data
		self.data[type] = utils.getfile(f'{config.loc.id}/{type}.json')
		if not self.data[type]:
			utils.log(f'No {type} data for location {config.loc.id}', 2)
			return

		# Index
		indexnow = utils.index("now", self.data[type])

		# Update msgqueue
		for map in config.map.get(type):

			# Alert
			if map[3] == 'graph':
				self.setalert(type, [ map, indexnow ])

	### SET MULTI
	def setmulti(self, src, map):
		data  = self.data[src]
		time  = map[1]
		idx   = map[2]
		max   = map[3]
		min   = map[4]
		prop  = map[5]

		if prop == 'hourly' or prop == 'daily':
			count = 1
		else:
			count = 0

		if not idx:
			utils.log('Index invalid, weather data is not up to date ...', 3)
			return

		# Cap to available data so we don't walk off the end of the array
		try:
			available = len(data[time][map[0][1][1]])
			end = idx + max if idx + max <= available else available
		except:
			end = idx + max

		for index in range(idx, end, 1):
			map[0][2][0] = prop
			self.setmap(src, map[0], index, count)
			count += 1

		count = -1
		for index in range(idx - 1, idx - min, -1):
			map[0][2][0] = prop
			self.setmap(src, map[0], index, count)
			count -= 1

	### SET MAP
	def setmap(self, src, map, idx=None, count=None, locid=None):
		data = self.data[src]

		# Property
		if idx is not None:
			if map[2][0] == 'day':
				property = f'{map[2][0]}{count}.{map[2][1]}'
			else:
				property = f'{map[2][0]}.{count}.{map[2][1]}'
		else:
			if locid:
				property = f'{map[2][0]}.{locid}.{map[2][1]}'
			else:
				property = f'{map[2][0]}.{map[2][1]}'

		# Content
		try:
			content = utils.getprop(data, map, idx, count)
		except TypeError as e:
			utils.log(f'{property}: {type(e).__name__} {e}', 4)
			utils.addprop(property, '')
		except Exception as e:
			utils.log(f'{property}: {type(e).__name__} {e}', 3)
			utils.addprop(property, '')
		else:
			utils.addprop(property, content)

	### GET MAP
	def getmap(self, type):

		# Layers disabled
		if not type == 'osm':
			if not utils.setting(f'map{type}', 'bool') or not utils.setting(f'loc{config.loc.id}maps', 'bool'):
				return

		# Check connectivity
		if not api.network():
			utils.log(f'[LOC{config.loc.id}] No network connectivity, maps not available ...', 3)
			return

		# Download
		utils.log(f'[LOC{config.loc.id}] Downloading map: {type}', 3)

		x, y  = utils.lat2coords(config.loc.lat, config.loc.lon, config.addon.mapzoom)
		tiles = [ [ x-1, y-1, 0, 0 ], [ x, y-1, 256, 0 ], [ x+1, y-1, 512, 0 ], [ x-1, y, 0, 256 ], [ x, y, 256, 256 ], [ x+1, y, 512, 256 ], [ x-1, y+1, 0, 512 ], [ x, y+1, 256, 512 ], [ x+1, y+1, 512, 512 ] ]
		dir   = f'{config.addon_cache}/{config.loc.id}'

		# IEM NEXRAD layers - download all frames
		if type == 'iemradar':
			frames = api.getiemframes()

			if not frames:
				utils.log(f'[LOC{config.loc.id}] IEM frames not available ...', 3)
				return

			# Ensure subfolder exists
			subdir = Path(f'{dir}/{type}')
			subdir.mkdir(parents=True, exist_ok=True)

			# Clear existing frames (IEM offsets are relative to "now", so all need refresh)
			for f in subdir.glob('*.png'):
				f.unlink()

			utils.log(f'[LOC{config.loc.id}] {type}: downloading {len(frames)} frames', 3)

			# Current time for synthetic timestamps (for file naming/sorting)
			now = utils.dt('nowutcstamp')

			for frame in frames:
				offset = frame['offset']
				layer = frame['layer']
				# Synthetic timestamp: now minus offset (in seconds)
				# This ensures files sort chronologically (oldest first)
				time = now - (offset * 60)

				config.mapcache[type] = {}
				map = []

				for count in range(0,9):
					s, w, n, e = utils.coords2bbox(tiles[count][0], tiles[count][1], config.addon.mapzoom)
					map.append([ config.loc.id, type, count, config.addon.mapzoom, tiles[count][0], tiles[count][1], tiles[count][2], tiles[count][3], layer, time, s, w, n, e ])

				# Download tiles for this frame
				with ThreadPoolExecutor(3) as pool:
					pool.map(api.getmap, map)

				# Merge tiles into single image
				api.mapmerge(map)
				config.mapcache[type] = {}

			# Cleanup old frames beyond history limit (in subfolder)
			files   = sorted(list(subdir.glob('*.png')), reverse=True)
			history = config.addon.maphistory

			for idx in range(0,100):
				try:
					file = files[idx]
				except:
					break
				else:
					if idx >= history:
						utils.log(f'[LOC{config.loc.id}] Removing old map: {file.stem}', 3)
						os.remove(file)

		# OSM base layer - single download
		else:
			time = utils.dt('nowutcstamp')
			path = None

			config.mapcache[type] = {}
			map = []

			for count in range(0,9):
				s, w, n, e = utils.coords2bbox(tiles[count][0], tiles[count][1], config.addon.mapzoom)
				map.append([ config.loc.id, type, count, config.addon.mapzoom, tiles[count][0], tiles[count][1], tiles[count][2], tiles[count][3], path, time, s, w, n, e ])

			with ThreadPoolExecutor(3) as pool:
				pool.map(api.getmap, map)

			api.mapmerge(map)
			config.mapcache[type] = {}

	### PROPERTIES
	def setother(self):

		# Maps
		index = 1

		for layer in config.map_layers:

			# Layers disabled
			if not utils.setting(f'map{layer}', 'bool') or not utils.setting(f'loc{config.loc.id}maps', 'bool'):
				for item in [ 'area', 'layer', 'layerpath', 'heading', 'time', 'legend' ]:
					utils.addprop(f'Map.{index}.{item}', '')
				utils.addprop(f'Map.{index}.FrameCount', 0)

				index += 1
				continue

			# Files - now in subfolder
			dir     = f'{config.addon_cache}/{config.loc.id}'
			subdir  = f'{dir}/{layer}'
			files   = sorted(list(Path(subdir).glob('*.png')), reverse=True) if Path(subdir).exists() else []
			history = config.addon.maphistory
			osm_exists = Path(f'{dir}/osm.png').exists()

			# Area (OSM base map exists independently from radar frames)
			if osm_exists:
				utils.addprop(f'Map.{index}.Area', f'{dir}/osm.png')
				utils.addprop(f'Map.{index}.Heading', config.localization.layers.get(layer))
				utils.addprop(f'Map.{index}.Legend', '')
			else:
				utils.addprop(f'Map.{index}.Area', '')
				utils.addprop(f'Map.{index}.Heading', '')
				utils.addprop(f'Map.{index}.Legend', '')

			# Layer (radar frames in subfolder)
			if files:
				ut   = int(files[0].stem)  # filename is now just {timestamp}.png
				tz   = utils.dt('stamploc', ut)
				date = tz.strftime(config.kodi.date)
				time = tz.strftime(config.kodi.time)

				utils.addprop(f'Map.{index}.Layer', f'{subdir}/{ut}.png')
				utils.addprop(f'Map.{index}.LayerPath', subdir)  # For multiimage animation
				utils.addprop(f'Map.{index}.Time', f'{date} {time}')
			else:
				utils.addprop(f'Map.{index}.Layer', '')
				utils.addprop(f'Map.{index}.LayerPath', '')
				utils.addprop(f'Map.{index}.Time', '')

			# Layers
			frame_count = 0
			for idx in range(0, history):

				try:
					file = files[idx]
				except:
					utils.addprop(f'Map.{index}.Layer.{idx}', '')
					utils.addprop(f'Map.{index}.Time.{idx}', '')
				else:
					ut   = int(file.stem)
					tz   = utils.dt('stamploc', ut)
					date = tz.strftime(config.kodi.date)
					time = tz.strftime(config.kodi.time)

					utils.addprop(f'Map.{index}.Layer.{idx}', f'{subdir}/{ut}.png')
					utils.addprop(f'Map.{index}.Time.{idx}', f'{date} {time}')
					frame_count += 1

			# Frame count for animation
			utils.addprop(f'Map.{index}.FrameCount', frame_count)

			index += 1

		# Locations
		utils.addprop('current.location', config.loc.name)
		utils.addprop('location', config.loc.name)
		self.setlocs()

		# Fetched
		for prop in [ 'current', 'weather', 'hourly', 'daily', 'timeofday', 'map' ]:
			utils.addprop(f'{prop}.isfetched', 'true')

		# Other
		utils.addprop('alerts', config.addon.alerts)
		utils.addprop('WeatherProvider', 'open-meteo.com, mesonet.agron.iastate.edu, met.no')
		utils.addprop('WeatherProviderLogo', f'{config.addon_path}/resources/banner.png')

	### NWS ALERTS (Set window properties)
	def setnwsalerts(self):
		if not utils.setting('noaalerts_enabled', 'bool'):
			utils.addprop('nws.alert.count', 0)
			return

		data = utils.getfile(f'{config.loc.id}/noaalerts.json')

		if not data:
			utils.log(f'[LOC{config.loc.id}] No NWS alert data', 3)
			utils.addprop('nws.alert.count', 0)
			return

		# Severity -> icon mapping (uses existing alert icon set)
		icon_map = {
			'Extreme':  'storm3',
			'Severe':   'storm2',
			'Moderate': 'storm1',
			'Minor':    'storm',
		}

		features = data.get('features', [])
		count    = 0

		for feature in features:
			p = feature.get('properties', {})

			# Skip non-active, cancelled, or past alerts
			status  = p.get('status', '')
			urgency = p.get('urgency', '')
			if status != 'Actual' or urgency == 'Past':
				continue

			severity = p.get('severity', 'Unknown')
			icon     = icon_map.get(severity, 'storm')
			expires  = p.get('expires') or p.get('ends') or ''

			if expires:
				try:
					expires = utils.conv_isodt(expires)
				except Exception:
					pass

			utils.addprop(f'nws.alert.{count}.event',    p.get('event', ''))
			utils.addprop(f'nws.alert.{count}.severity', severity)
			utils.addprop(f'nws.alert.{count}.urgency',  urgency)
			utils.addprop(f'nws.alert.{count}.headline', p.get('headline', ''))
			utils.addprop(f'nws.alert.{count}.areadesc', p.get('areaDesc', ''))
			utils.addprop(f'nws.alert.{count}.expires',  expires)
			utils.addprop(f'nws.alert.{count}.icon',     f'{config.addon_icons}/alert/{icon}.png')

			utils.log(f'[LOC{config.loc.id}] NWS alert {count}: {p.get("event")} ({severity})', 3)
			count += 1

		utils.addprop('nws.alert.count', count)
		utils.log(f'[LOC{config.loc.id}] NWS alerts: {count} active', 3)

	### NWS ALERTS (Notification queue)
	def nwsalertqueue(self):
		if not utils.setting('noaalerts_enabled', 'bool'):
			return

		if not utils.setting(f'loc{config.loc.id}alert', 'bool'):
			return

		data = utils.getfile(f'{config.loc.id}/noaalerts.json')

		if not data:
			return

		# Severity -> notification level (matches existing notice/caution/danger)
		level_map = {
			'Extreme':  3,
			'Severe':   3,
			'Moderate': 2,
			'Minor':    1,
		}

		icon_map = {
			'Extreme':  'storm3',
			'Severe':   'storm2',
			'Moderate': 'storm1',
			'Minor':    'storm',
		}

		features = data.get('features', [])

		for feature in features:
			p        = feature.get('properties', {})
			status   = p.get('status', '')
			urgency  = p.get('urgency', '')
			severity = p.get('severity', 'Unknown')

			if status != 'Actual' or urgency == 'Past':
				continue

			level    = level_map.get(severity, 1)
			icon     = icon_map.get(severity, 'storm')
			event    = p.get('event', '')
			headline = p.get('headline', '') or event

			if level == 1 and not utils.setting('noaalerts_notice', 'bool'):
				continue
			if level == 2 and not utils.setting('noaalerts_caution', 'bool'):
				continue
			if level == 3 and not utils.setting('noaalerts_danger', 'bool'):
				continue

			header = f'{config.loc.short} - {event}'
			msg    = headline[:120]

			config.addon.msgqueue.append([
				header,
				msg,
				f'{config.addon_icons}/alert/{icon}.png'
			])

	### NOTIFICATION
	def notification(self):
		queue    = config.addon.msgqueue
		duration = utils.setting('alert_duration', 'int')

		if queue:
			for alert in queue:
				utils.notification(alert[0], alert[1], alert[2], config.loc.id)
				utils.monitor.waitForAbort(duration)
				if utils.monitor.abortRequested():
					utils.log(f'Abort requested ...', 3)
					break

