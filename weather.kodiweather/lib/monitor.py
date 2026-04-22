import xbmc

from pathlib import Path

from . import config
from . import utils
from . import weather

### MONITOR
class Main(xbmc.Monitor):

	def __init__(self, *args, **kwargs):
		self.old = None

	def onSettingsChanged(self):
		current = utils.settings(changed=True)

		if self.old:
			if self.old != current:
				utils.log('Settings changed, refreshing ...')
				config.init()
				weather.Main(str(utils.settingrpc("weather.currentlocation") or 1), mode='update')

				# Map zoom
				if current.get('mapzoom') != self.old.get('mapzoom'):
					utils.log('Map zoom changed, re-downloading ...')

					for locid in range(1, config.addon.maxlocs):
						if utils.setting(f'loc{locid}'):
							utils.setsetting(f'loc{locid}map', '321318000')
							utils.setsetting(f'loc{locid}rv', '321318000')
							utils.setsetting(f'loc{locid}gc', '321318000')

				# Map provider changed - re-download base maps
				if current.get('mapprovider') != self.old.get('mapprovider'):
					utils.log('Map provider changed, re-downloading base maps ...')

					for locid in range(1, config.addon.maxlocs):
						if utils.setting(f'loc{locid}'):
							utils.setsetting(f'loc{locid}map', '321318000')

		self.old = current

	def waitForService(self):
		sleep = 0

		while not self.abortRequested() and utils.setting('service') != 'idle':
			utils.log(f'Waiting for service thread: {utils.setting("service")}', 3)
			sleep += 1

			if sleep == 30:
				utils.log(f'Service thread not responding ...', 2)
				return

			self.waitForAbort(1)

