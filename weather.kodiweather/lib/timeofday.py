"""Time-of-day and daily-overview properties (morning / afternoon / evening / night blocks, the daily.N.* overview and the
personalised forecast window).

Moved out of utils.getprop() unchanged (only the indentation moved). Called through getprop for the map row of kind "timeofday".
"""
from statistics import StatisticsError, mean, mode

from . import config
from . import conv
from .utils import addprop, dt, index


def build(data, map):
	idxnow  = index("now", data)
	idxmid  = index("mid", data)
	idxday  = index("mid", data)
	tod     = { 0: 'night', 1: 'morning', 2: 'afternoon', 3: 'evening' }
	start   = False
	content = 'true'
	idxtod  = 1
	idxtod2 = 1
	idxtod3 = 1

	for d in range(0, config.maxdays):
		l   = []
		ll  = []

		# Daily
		for c in range(idxday, idxday+24):

			try:
				v  = data[map[1][0]][map[1][1]][c]
				vv = data[map[1][0]]['temperature_2m'][c]
			except (KeyError, IndexError, TypeError):
				for i in [ 'date', 'shortdate', 'weekday', 'weekdayshort', 'condition', 'outlook', 'outlookicon', 'temperature', 'maxoutlook', 'maxoutlookicon' ]:
					addprop(f'daily.{idxtod3}.overview.{i}', '')
				continue
			else:
				l.append(v)
				ll.append(vv)

		# Personalized forecast
		fcstart = config.map_fcstart.get(config.addon.fcstart)
		fcend   = config.map_fcend.get(config.addon.fcend)

		l_full = list(l)  # full 24h window; used for worst-case daily card condition
		l = l[fcstart:][:fcend]

		# Skip day if no hourly data available (days beyond 72-hour window)
		if not l or not ll:
			for i in [ 'date', 'shortdate', 'weekday', 'weekdayshort', 'condition', 'outlook', 'outlookicon', 'temperature', 'maxoutlook', 'maxoutlookicon', 'fanartcode' ]:
				addprop(f'daily.{idxtod3}.overview.{i}', '')
				addprop(f'daily.{idxtod3}.{i}', '')
				addprop(f'day{idxtod3-1}.{i}', '')
			idxday += 24
			idxtod3 += 1
			continue

		# Properties
		date  = data[map[1][0]]['time'][idxday]
		try:
			code = mode(sorted(l, reverse=True))
		except StatisticsError:
			code = max(l)  # Fallback to most severe condition
		mcode      = max(l)
		mcode_full = max(l_full)  # worst condition of the full 24h day
		temp  = conv.temp(mean(ll))

		addprop(f'daily.{idxtod3}.overview.date', dt('stamploc', date).strftime(config.kodi.date))
		addprop(f'daily.{idxtod3}.overview.shortdate', dt('stamploc', date).strftime(config.kodi.date))
		addprop(f'daily.{idxtod3}.overview.weekday', config.localization.weekday.get(dt('stamploc', date).strftime('%u')))
		addprop(f'daily.{idxtod3}.overview.weekdayshort', config.localization.weekdayshort.get(dt('stamploc', date).strftime('%u')))
		addprop(f'daily.{idxtod3}.overview.temperature', temp)
		addprop(f'daily.{idxtod3}.overview.outlook', config.localization.wmo.get(f'{code}d'))
		addprop(f'daily.{idxtod3}.overview.outlookicon', f'{config.safe_fanart_code(code, "d") or config.map_wmo.get(f"{code}d")}.png')
		addprop(f'daily.{idxtod3}.overview.fanartcode', config.safe_fanart_code(code, 'd') or '')

		# Overwrite forecast (personalized)
		addprop(f'daily.{idxtod3}.condition', config.localization.wmo.get(f'{code}d'))
		addprop(f'daily.{idxtod3}.outlook', config.localization.wmo.get(f'{code}d'))
		addprop(f'daily.{idxtod3}.outlookicon', f'{config.safe_fanart_code(code, "d") or config.map_wmo.get(f"{code}d")}.png')
		addprop(f'daily.{idxtod3}.fanartcode', config.safe_fanart_code(code, 'd') or '')

		addprop(f'day{idxtod3-1}.condition', config.localization.wmo.get(f'{mcode_full}d'))
		addprop(f'day{idxtod3-1}.outlook', config.localization.wmo.get(f'{mcode_full}d'))
		addprop(f'day{idxtod3-1}.outlookicon', f'resource://resource.images.weathericons.default/{config.safe_fanart_code(mcode_full, "d") or config.map_wmo.get(f"{mcode_full}d")}.png')
		addprop(f'day{idxtod3-1}.fanartcode', config.safe_fanart_code(mcode_full, 'd') or '')

		# Max outlook — full-day worst vs personalized-window typical
		if mcode_full > code:
			addprop(f'daily.{idxtod3}.overview.maxoutlook', config.localization.wmo.get(f'{mcode_full}d'))
			addprop(f'daily.{idxtod3}.overview.maxoutlookicon', f'{config.safe_fanart_code(mcode_full, "d") or config.map_wmo.get(f"{mcode_full}d")}.png')

			addprop(f'daily.{idxtod3}.maxoutlook', config.localization.wmo.get(f'{mcode_full}d'))
			addprop(f'daily.{idxtod3}.maxoutlookicon', f'{config.safe_fanart_code(mcode_full, "d") or config.map_wmo.get(f"{mcode_full}d")}.png')

		else:
			addprop(f'daily.{idxtod3}.overview.maxoutlook', '')
			addprop(f'daily.{idxtod3}.overview.maxoutlookicon', '')

			addprop(f'daily.{idxtod3}.maxoutlook', '')
			addprop(f'daily.{idxtod3}.maxoutlookicon', '')

		idxday += 24
		idxtod3 += 1

		# Hourly
		for t in range(0,4):
			l   = []
			ll  = []
			lll = []
			llll = []
			now = ''

			for c in range(idxmid, idxmid+6):

				try:
					v   = data[map[1][0]][map[1][1]][c]
					vv  = data[map[1][0]]['is_day'][c]
					vvv = data[map[1][0]]['temperature_2m'][c]
					vvvv = data[map[1][0]]['time'][c]
				except (KeyError, IndexError, TypeError):
					continue
				else:
					l.append(v)
					ll.append(vv)
					lll.append(vvv)
					llll.append(vvvv)

					if idxnow == c:
						start = True
						now   = 'true'

			# Skip this time slot if no data available (beyond 72-hour window)
			if not l or not ll or not lll:
				idxmid += 6
				continue

			date  = data[map[1][0]]['time'][idxmid]
			try:
				code = mode(sorted(l, reverse=True))
			except StatisticsError:
				code = max(l)  # Fallback to most severe condition
			mcode = max(l)
			try:
				isday = mode(sorted(ll, reverse=False))
			except StatisticsError:
				isday = ll[0] if ll else 1  # Fallback to first value or daytime
			isday = 'n' if isday == 0 else 'd'
			temp  = conv.temp(mean(lll))

			# TimeOfDay (List)
			if start:
				addprop(f'timeofday.{idxtod}.date', dt('stamploc', date).strftime(config.kodi.date))
				addprop(f'timeofday.{idxtod}.shortdate', dt('stamploc', date).strftime(config.kodi.date))
				addprop(f'timeofday.{idxtod}.weekday', config.localization.weekday.get(dt('stamploc', date).strftime('%u')))
				addprop(f'timeofday.{idxtod}.weekdayshort', config.localization.weekdayshort.get(dt('stamploc', date).strftime('%u')))
				addprop(f'timeofday.{idxtod}.time', config.localization.timeofday.get(t))
				addprop(f'timeofday.{idxtod}.outlook', config.localization.wmo.get(f'{code}{isday}'))
				addprop(f'timeofday.{idxtod}.outlookicon', f'{config.safe_fanart_code(code, isday) or config.map_wmo.get(f"{code}{isday}")}.png')
				addprop(f'timeofday.{idxtod}.fanartcode', config.safe_fanart_code(code, isday) or '')
				addprop(f'timeofday.{idxtod}.temperature', temp)

				if mcode > code:
					addprop(f'timeofday.{idxtod}.maxoutlook', config.localization.wmo.get(f'{mcode}{isday}'))
					addprop(f'timeofday.{idxtod}.maxoutlookicon', f'{config.safe_fanart_code(mcode, isday) or config.map_wmo.get(f"{mcode}{isday}")}.png')
				else:
					addprop(f'timeofday.{idxtod}.maxoutlook', '')
					addprop(f'timeofday.{idxtod}.maxoutlookicon', '')

				idxtod += 1

			# TimeOfDay (Daily)
			addprop(f'daily.{idxtod2}.{tod.get(t)}.date', dt('stamploc', date).strftime(config.kodi.date))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.shortdate', dt('stamploc', date).strftime(config.kodi.date))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.weekday', config.localization.weekday.get(dt('stamploc', date).strftime('%u')))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.weekdayshort', config.localization.weekdayshort.get(dt('stamploc', date).strftime('%u')))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.time', config.localization.timeofday.get(t))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.outlook', config.localization.wmo.get(f'{code}{isday}'))
			addprop(f'daily.{idxtod2}.{tod.get(t)}.outlookicon', f'{config.safe_fanart_code(code, isday) or config.map_wmo.get(f"{code}{isday}")}.png')
			addprop(f'daily.{idxtod2}.{tod.get(t)}.fanartcode', config.safe_fanart_code(code, isday) or '')
			addprop(f'daily.{idxtod2}.{tod.get(t)}.temperature', temp)

			if mcode > code:
				addprop(f'daily.{idxtod2}.{tod.get(t)}.maxoutlook', config.localization.wmo.get(f'{mcode}{isday}'))
				addprop(f'daily.{idxtod2}.{tod.get(t)}.maxoutlookicon', f'{config.safe_fanart_code(mcode, isday) or config.map_wmo.get(f"{mcode}{isday}")}.png')
			else:
				addprop(f'daily.{idxtod2}.{tod.get(t)}.maxoutlook', '')
				addprop(f'daily.{idxtod2}.{tod.get(t)}.maxoutlookicon', '')

			if d == 0:
				addprop(f'daily.{idxtod2}.{tod.get(t)}.now', now)

			idxmid  += 6

		idxtod2 += 1

	return content
