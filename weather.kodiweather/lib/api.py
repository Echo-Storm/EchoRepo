import os
import io
import socket
import json
import requests
import xbmc
import xbmcgui

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from requests.adapters import HTTPAdapter, Retry

from . import config
from . import utils
from . import weather

# DNS cache
old_getaddrinfo = socket.getaddrinfo

def new_getaddrinfo(*args):
	try:
		return config.dnscache[args]
	except KeyError:
		r = old_getaddrinfo(*args)
		config.dnscache[args] = r
		return r

socket.getaddrinfo = new_getaddrinfo

# Requests
r = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
s = requests.Session()
s.headers.update(config.addon_ua)
s.mount('https://', HTTPAdapter(max_retries=r))

# Network
def network():
	if config.neterr > 10:
		return False
	else:
		return True

# Get url
def geturl(url, head=False):

	# Network timeout
	if network():
		timeout = 6
	else:
		timeout = 1

	# Download
	try:
		if head:
			utils.log(f'Checking: {url}', 3)
			r = s.head(url, timeout=timeout)
		else:
			utils.log(f'Download: {url}', 3)
			r = s.get(url, timeout=timeout)

	except Exception as e:
		utils.log(f'Download: {url} ({e})', 3)
		config.dnscache = {}
		config.neterr  += 1
		return None

	else:
		config.neterr = 0

		if r.ok:
			utils.log(f'Download: {url} ({r.status_code})', 3)
			return r.content
		else:
			utils.log(f'Download: {url} ({r.status_code})', 2)
			config.dnscache = {}
			return None

# Get data
def getdata(type, loc, map=None):

	# URL
	if type == 'weather':
		url = config.map_api.get(type).format(map[0], map[1], config.maxdays)
	elif type == 'airquality':
		url = config.map_api.get(type).format(map[0], map[1])
	elif type == 'sun':
		url = config.map_api.get(type).format(map[0], map[1], map[2])
	elif type == 'moon':
		url = config.map_api.get(type).format(map[0], map[1], map[2])

	# Weather
	file = f'{config.addon_cache}/{loc}/{type}.json'
	data = geturl(url)

	if data:
		with open(Path(file), 'wb') as f:
			f.write(data)

# Get NWS Alerts
def getnoaalerts(locid, lat, lon):
	url  = config.map_api.get('noaalerts').format(round(lat, 4), round(lon, 4))
	file = f'{config.addon_cache}/{locid}/noaalerts.json'

	utils.log(f'[LOC{locid}] Downloading NWS alerts: {url}', 3)
	data = geturl(url)

	if data:
		with open(Path(file), 'wb') as f:
			f.write(data)


def getmap(map, head=False):

	if map[1] == 'osm':
		# Use selected map provider (defaults to osm)
		provider = config.addon.mapprovider
		url_template = config.map_providers.get(provider, config.map_providers['osm'])
		url = url_template.format(map[3], map[4], map[5])
	elif map[1] == 'iemradar':
		# IEM NEXRAD tiles - load balance across 3 servers
		import random
		server = random.choice(['1', '2', '3'])
		layer = map[8]  # Layer name (e.g., 'nexrad-n0q' or 'nexrad-n0q-m05m')
		url = config.map_api.get('iemradar').format(server, layer, map[3], map[4], map[5])
	elif map[1] == 'gctemp':
		url = config.map_api.get(map[1]).format(map[10], map[11], map[12], map[13])
	elif map[1] == 'gcwind':
		url = config.map_api.get(map[1]).format(map[10], map[11], map[12], map[13])

	# HEAD
	if head:
		data = geturl(url, head=True)
		return data

	# GET
	data = geturl(url)

	if data:
		config.mapcache[map[1]][map[2]] = data
	else:
		with open(Path(f'{config.addon_path}/resources/tile.png'), 'rb') as f:
			tile = f.read()

		config.mapcache[map[1]][map[2]] = tile

# Map merge
def mapmerge(map):
	image = Image.new("RGBA", (756, 756), None)

	for item in map:

		try:
			tile = Image.open(io.BytesIO(config.mapcache[item[1]][item[2]]))
		except:
			tile = Image.open(f'{config.addon_path}/resources/tile.png')
		
		image.paste(tile, (item[6], item[7]))

	if map[0][1] == 'osm':
		image.save(f'{config.addon_cache}/{map[0][0]}/{map[0][1]}.png')
	else:
		# Burn timestamp into radar/satellite frames
		try:
			ut = map[0][9]
			tz = utils.dt('stamploc', ut)
			timestamp = tz.strftime(f'{config.kodi.date} {config.kodi.time}')

			draw = ImageDraw.Draw(image)

			# Try to load a font, fall back to default
			try:
				font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
			except:
				try:
					font = ImageFont.truetype('arial.ttf', 28)
				except:
					font = ImageFont.load_default()

			# Position: right side, adjusted for best visibility
			x = image.width - 450
			y = image.height - 250

			# Draw shadow then text (simple approach)
			draw.text((x+2, y+2), timestamp, font=font, fill=(0, 0, 0, 255))
			draw.text((x, y), timestamp, font=font, fill=(255, 255, 255, 255))
		except Exception as e:
			utils.log(f'Timestamp burn failed: {e}', 3)

		# Save radar/satellite frames in subfolder for multiimage animation
		subdir = Path(f'{config.addon_cache}/{map[0][0]}/{map[0][1]}')
		subdir.mkdir(parents=True, exist_ok=True)
		savepath = f'{subdir}/{map[0][9]}.png'
		try:
			image.save(savepath)
			utils.log(f'Saved radar frame: {savepath}', 3)
		except Exception as e:
			utils.log(f'Failed to save radar frame {savepath}: {e}', 3)

# Get rvdata - returns list of all available frames [{time, path}, ...]
# Get IEM NEXRAD frame list
def getiemframes():
	"""
	Returns list of IEM NEXRAD frames with layer names and offsets.
	IEM provides fixed offsets: current, 5min ago, 10min ago, etc. up to 55min.
	No API query needed - these are static layer names.
	"""
	frames = []
	for offset in config.iem_frame_offsets:
		if offset == 0:
			layer = 'nexrad-n0q'
		else:
			layer = f'nexrad-n0q-m{offset:02d}m'
		frames.append({'offset': offset, 'layer': layer})
	return frames

# Get location (GeoIP)
def getloc(locid):
	utils.log(f'Geolocation ...')

	# Get location
	try:
		data    = json.loads(geturl(config.map_api.get('geoip')))
		city    = data['city']
		region  = data.get('regionName')
		country = data.get('countryCode')

		# Search
		data     = json.loads(geturl(config.map_api.get('search').format(city)))
		location = data['results'][0]

		for item in data['results']:

			if country and region:
				if country in item['country_code'] and region in item['admin1']:
					location = item
					break

			elif country:
				if country in item['country_code']:
					location = item
					break
	except Exception as e:
		utils.log(f'Geolocation: Unknown ({e})')
	else:
		utils.log(f'Geolocation: {location["name"]}, {location["admin1"]}, {location["country_code"]} [{location["latitude"]}, {location["longitude"]}]')
		utils.setsetting(f'loc{locid}', f'{location["name"]}, {location["admin1"]}, {location["country_code"]}')
		utils.setsetting(f'loc{locid}lat', str(location["latitude"]))
		utils.setsetting(f'loc{locid}lon', str(location["longitude"]))
		utils.setsetting(f'loc{locid}tz', str(location["timezone"]))

# Clear location
def clearloc(locid, last=False):
	if last:
		utils.setsetting(f'loc{locid}data', '321318000')
		utils.setsetting(f'loc{locid}map', '321318000')
		utils.setsetting(f'loc{locid}rv', '321318000')
		utils.setsetting(f'loc{locid}gc', '321318000')
	else:
		utils.setsetting(f'loc{locid}', '')
		utils.setsetting(f'loc{locid}user', '')
		utils.setsetting(f'loc{locid}alert', 'true')
		utils.setsetting(f'loc{locid}utz', 'false')
		utils.setsetting(f'loc{locid}tz', '')
		utils.setsetting(f'loc{locid}lat', '0')
		utils.setsetting(f'loc{locid}lon', '0')

# Set location
def setloc (locid):
	utils.log(f'Search dialog ...')

	dialog   = xbmcgui.Dialog()
	input    = utils.setting(f'loc{locid}')
	keyboard = xbmc.Keyboard(input, utils.loc(14024), False)
	keyboard.doModal()

	if keyboard.isConfirmed():
		search = keyboard.getText()

		# No changes
		if search == input:
			utils.log(f'[LOC{locid}] No changes')

		# Remove location
		elif search == '':
			check = utils.setting(f'loc{int(locid)+1}')

			if not check:
				utils.log(f'[LOC{locid}] Removed')
				clearloc(locid)
				clearloc(locid, True)

		# Search location
		else:
			try:
				locs   = []
				url    = config.map_api.get('search').format(search)
				data   = json.loads(geturl(url))['results']
			except:
				utils.log(f'[LOC{locid}] No results')
				dialog.ok('Kodi Weather', utils.loc(284))
			else:
				for item in data:
					li = xbmcgui.ListItem(f'{item.get("name")}, {item.get("admin1")}, {item.get("country_code")} (Lat: {item.get("latitude")}, Lon: {item.get("longitude")})')
					locs.append(li)

				select = dialog.select(utils.loc(396), locs, useDetails=True)

				if select != -1:

					# Cleanup cache dir (handle both files and subdirectories)
					import shutil
					dir = f'{config.addon_cache}/{locid}'
					for item in Path(dir).glob('*'):
						if item.is_file():
							item.unlink()
						elif item.is_dir():
							shutil.rmtree(item)

					# Set location
					utils.log(f'Location {locid}: {data[select].get("name")}, {data[select].get("admin1")}, {data[select].get("country_code")} {data[select].get("latitude")} {data[select].get("longitude")}')
					utils.setsetting(f'loc{locid}', f'{data[select].get("name")}, {data[select].get("admin1")}, {data[select].get("country_code")}')
					utils.setsetting(f'loc{locid}lat', data[select]["latitude"])
					utils.setsetting(f'loc{locid}lon', data[select]["longitude"])
					utils.setsetting(f'loc{locid}tz', data[select]["timezone"])

					# Wait for settings dialog
					while xbmcgui.getCurrentWindowDialogId() == 10140:
						utils.log(f'Waiting for settings dialog ...')
						utils.monitor.waitForAbort(1)

						if utils.monitor.abortRequested():
							return

					# Cleanup lastupdate
					clearloc(locid, True)

					# Refresh
					if int(utils.settingrpc("weather.currentlocation")) == int(locid):
						weather.Main(str(locid), mode='download')
						weather.Main(str(locid), mode='update')
					else:
						weather.Main(str(locid), mode='download')
						weather.Main(str(locid), mode='updatelocs')

