import json
import sys

import xbmc
import xbmcaddon
import xbmcgui


def rpc(method, params=None):
	return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))


def nextlocation():
	"""Switch Kodi's weather to the next location that is set up, and publish its (cached) data at once.
	The service keeps every location's data downloaded, so the 'update' run only reads files and takes well under a second."""
	count = int(xbmc.getInfoLabel('Window(Weather).Property(Locations)') or 1)
	current = rpc('Settings.GetSettingValue', {'setting': 'weather.currentlocation'}).get('result', {}).get('value', 1)
	new = current % count + 1
	rpc('Settings.SetSettingValue', {'setting': 'weather.currentlocation', 'value': new})
	from lib import config, weather
	config.init(cache=True)
	weather.Main(str(new), mode='update')


def main():
	if 'location' in sys.argv[1:]:
		nextlocation()
		return
	path = xbmcaddon.Addon('weather.kodiweather').getAddonInfo('path')
	win = xbmcgui.WindowXML('script-kodiweather-main.xml', path, 'default', '1080i')
	win.doModal()
	del win


if (__name__ == '__main__'):
	main()
