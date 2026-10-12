import sys

# Kodi calls this with the location number to fetch; run with no number (RunScript(weather.kodiweather)) it opens the weather screen
if (__name__ == '__main__'):
	if len(sys.argv) > 1 and sys.argv[1].isdigit():
		from lib import weather
		from lib import config
		config.init(cache=True)
		weather.Main(sys.argv[1])
	else:
		import screen
		screen.main()
