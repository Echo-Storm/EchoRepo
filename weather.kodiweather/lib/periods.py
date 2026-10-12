"""Kodi weather window blocks the skins read: 36Hour.*, Weekend.* and Updated.

Built from the same cached open-meteo data as everything else, with the same unit conversion helpers, and added to the
property buffer with utils.addprop() (flushed by utils.setprops() like all other properties).

36Hour:  three consecutive 12-hour blocks, day = 06:00-18:00 and night = 18:00-06:00 local time, starting with the block
         that contains "now" (Today / Tonight / Tomorrow ...). Day blocks report the high, night blocks the low.
Weekend: the next Saturday and Sunday (today counts when it is one of them), from the daily and hourly arrays.
Hourly extras: Hourly.N.HeatIndex and Hourly.N.WindChill (NWS formulas; empty when they do not apply), read by the old custom window.
"""
from datetime import timedelta
from math import sqrt
from pathlib import Path

from . import config
from . import conv
from . import utils

DAY_START = 6
DAY_END = 18


def _clean(h, key, idx):
	series = h.get(key) or []
	return [series[i] for i in idx if i < len(series) and series[i] is not None]


def _fmt_temp(v):
	return f'{conv.temp(v)}{conv.temp()}'


def _fmt_speed(v):
	return f'{conv.speed(v)} {conv.speed()}'


def _worst(codes):
	"""Same rule as the daily cards: the worst (highest) WMO code of the period."""
	return max(codes) if codes else None


def _outlook(code, isday):
	"""(condition text, icon, fanart code) for a WMO code, or empty strings."""
	if code is None:
		return '', '', ''
	text = config.localization.wmo.get(f'{code}{isday}') or ''
	kodi_code = config.map_wmo.get(f'{code}{isday}')
	icon = f'{config.get_fanart_folder(kodi_code)}.png' if kodi_code is not None else ''
	fanart = config.safe_fanart_code(code, isday)
	return text, icon, '' if fanart is None else fanart


def _wind(h, idx):
	"""(speed text, direction text, degree text) at the windiest hour of the period."""
	speeds = h.get('wind_speed_10m') or []
	dirs = h.get('wind_direction_10m') or []
	best = None
	for i in idx:
		if i < len(speeds) and speeds[i] is not None and (best is None or speeds[i] > speeds[best]):
			best = i
	if best is None:
		return '', '', ''
	deg = dirs[best] if best < len(dirs) and dirs[best] is not None else None
	if deg is None:
		return _fmt_speed(speeds[best]), '', ''
	return _fmt_speed(speeds[best]), conv.direction(deg), f'{int(round(deg))}°'


def _block(h, idx, day):
	"""Properties common to a 36Hour block and a Weekend day, from hourly indexes."""
	isday = 'd' if day else 'n'
	temps = _clean(h, 'temperature_2m', idx)
	feels = _clean(h, 'apparent_temperature', idx)
	hum = _clean(h, 'relative_humidity_2m', idx)
	prec = _clean(h, 'precipitation_probability', idx)
	text, icon, fanart = _outlook(_worst(_clean(h, 'weather_code', idx)), isday)
	wspeed, wdir, wdeg = _wind(h, idx)
	return {
		'temps': temps,
		'Outlook': text,
		'OutlookIcon': icon,
		'FanartCode': fanart,
		'Precipitation': f'{int(round(max(prec)))}%' if prec else '',
		'Humidity': f'{int(round(sum(hum) / len(hum)))}%' if hum else '',
		'FeelsLike': _fmt_temp(sum(feels) / len(feels)) if feels else '',
		'WindSpeed': wspeed,
		'WindDirection': wdir,
		'WindDegree': wdeg,
	}


def _hour_indexes(h, start, end):
	"""Indexes of the hourly entries whose local time is in [start, end)."""
	out = []
	for i, t in enumerate(h.get('time') or []):
		if start <= utils.dt('stamploc', t) < end:
			out.append(i)
	return out


def set36hour(data, now):
	h = data.get('hourly') or {}
	midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
	if DAY_START <= now.hour < DAY_END:
		blocks = [(midnight + timedelta(hours=DAY_START), True, 'This Afternoon' if now.hour >= 12 else 'Today'),
		          (midnight + timedelta(hours=DAY_END), False, 'Tonight'),
		          (midnight + timedelta(hours=24 + DAY_START), True, 'Tomorrow')]
	elif now.hour >= DAY_END:
		blocks = [(midnight + timedelta(hours=DAY_END), False, 'Tonight'),
		          (midnight + timedelta(hours=24 + DAY_START), True, 'Tomorrow'),
		          (midnight + timedelta(hours=24 + DAY_END), False, 'Tomorrow Night')]
	else:
		# after midnight the night block that started yesterday evening is still running
		blocks = [(midnight - timedelta(hours=24 - DAY_END), False, 'Overnight'),
		          (midnight + timedelta(hours=DAY_START), True, 'Today'),
		          (midnight + timedelta(hours=DAY_END), False, 'Tonight')]
	built = 0
	for n, (start, day, heading) in enumerate(blocks, start=1):
		idx = _hour_indexes(h, start, start + timedelta(hours=12))
		if not idx:
			continue
		b = _block(h, idx, day)
		if not b['temps']:
			continue
		p = f'36Hour.{n}.'
		utils.addprop(p + 'Heading', heading)
		utils.addprop(p + 'TemperatureHeading', 'High' if day else 'Low')
		utils.addprop(p + 'Temperature', _fmt_temp(max(b['temps']) if day else min(b['temps'])))
		for key in ('Outlook', 'OutlookIcon', 'FanartCode', 'Precipitation', 'Humidity', 'FeelsLike', 'WindSpeed', 'WindDirection', 'WindDegree'):
			utils.addprop(p + key, b[key])
		built += 1
	if built:
		utils.addprop('36Hour.IsFetched', 'true')


def setweekend(data, now):
	h, d = data.get('hourly') or {}, data.get('daily') or {}
	days = {}
	for i, t in enumerate(d.get('time') or []):
		days.setdefault(utils.dt('stamploc', t).date(), i)
	# next Saturday (5) and Sunday (6), today included
	today = now.date()
	saturday = today + timedelta(days=(5 - today.weekday()) % 7) if today.weekday() != 6 else today - timedelta(days=1)
	built = 0
	for n, date in enumerate((saturday, saturday + timedelta(days=1)), start=1):
		i = days.get(date)
		if i is None:
			continue
		start = now.replace(year=date.year, month=date.month, day=date.day, hour=0, minute=0, second=0, microsecond=0)
		b = _block(h, _hour_indexes(h, start, start + timedelta(hours=24)), True)
		hi, lo = (d.get('temperature_2m_max') or [None] * (i + 1))[i], (d.get('temperature_2m_min') or [None] * (i + 1))[i]
		code = (d.get('weather_code') or [None] * (i + 1))[i]
		if code is not None:
			b['Outlook'], b['OutlookIcon'], b['FanartCode'] = _outlook(code, 'd')
		chance = (d.get('precipitation_probability_max') or [None] * (i + 1))[i]
		p = f'Weekend.{n}.'
		stamp = d['time'][i]
		utils.addprop(p + 'ShortDate', utils.dt('stamploc', stamp).strftime(config.kodi.date))
		utils.addprop(p + 'LongDate', utils.dt('stamploc', stamp).strftime(config.kodi.date))
		utils.addprop(p + 'ShortDay', config.localization.weekdayshort.get(utils.dt('stamploc', stamp).strftime('%u'), ''))
		utils.addprop(p + 'LongDay', config.localization.weekday.get(utils.dt('stamploc', stamp).strftime('%u'), ''))
		utils.addprop(p + 'HighTemperature', _fmt_temp(hi) if hi is not None else '')
		utils.addprop(p + 'LowTemperature', _fmt_temp(lo) if lo is not None else '')
		utils.addprop(p + 'ChancePrecipitation', f'{int(round(chance))}%' if chance is not None else b['Precipitation'])
		for key in ('Outlook', 'OutlookIcon', 'FanartCode', 'Precipitation', 'Humidity', 'WindSpeed', 'WindDirection', 'WindDegree'):
			utils.addprop(p + key, b[key])
		built += 1
	if built:
		utils.addprop('Weekend.IsFetched', 'true')


def _heat_index_f(t, rh):
	"""NWS (Rothfusz) heat index in deg F, or None when it does not apply (below 80 F or 40 % humidity)."""
	if t < 80 or rh < 40:
		return None
	hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh - 0.00683783 * t * t
	      - 0.05481717 * rh * rh + 0.00122874 * t * t * rh + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
	if rh < 13 and t <= 112:
		hi -= ((13 - rh) / 4) * sqrt((17 - abs(t - 95)) / 17)
	elif rh > 85 and t <= 87:
		hi += ((rh - 85) / 10) * ((87 - t) / 5)
	return hi


def _wind_chill_f(t, mph):
	"""NWS wind chill in deg F, or None when it does not apply (above 50 F or wind of 3 mph or less)."""
	if t > 50 or mph <= 3:
		return None
	v = mph ** 0.16
	return 35.74 + 0.6215 * t - 35.75 * v + 0.4275 * t * v


def _display_f(deg_f):
	"""A deg F value in the user's unit with the unit sign, like the other temperature properties."""
	if deg_f is None:
		return ''
	return _fmt_temp((deg_f - 32) / 1.8)


def sethourlyextras(data, now):
	h = data.get('hourly') or {}
	now = utils.index('now', data)
	if now is None:
		return
	temps, hum, wind = h.get('temperature_2m') or [], h.get('relative_humidity_2m') or [], h.get('wind_speed_10m') or []
	for n in range(1, config.maxhours + 1):
		i = now + n - 1
		heat = chill = None
		try:
			t_f = temps[i] * 1.8 + 32
			if hum[i] is not None:
				heat = _heat_index_f(t_f, hum[i])
			if wind[i] is not None:
				chill = _wind_chill_f(t_f, wind[i] * 0.621371)      # open-meteo wind is km/h
		except (IndexError, TypeError):
			pass
		utils.addprop(f'Hourly.{n}.HeatIndex', _display_f(heat))
		utils.addprop(f'Hourly.{n}.WindChill', _display_f(chill))


def setupdated(cachefile):
	"""Kodi's "Updated" property: when the forecast data was last fetched."""
	try:
		stamp = int(Path(cachefile).stat().st_mtime)
	except OSError:
		return
	when = utils.dt('stamploc', stamp)
	utils.addprop('Updated', f'{when.strftime(config.kodi.date)} {conv.time("time", stamp)}')


def setperiods(data, cachefile=None):
	"""Entry point: called after the weather data has been mapped."""
	if not data or not (data.get('hourly') or {}).get('time'):
		return
	now = utils.dt('nowloc')
	for fn in (set36hour, setweekend, sethourlyextras):
		try:
			fn(data, now)
		except Exception as e:  # a block that cannot be built must not stop the others or the update
			utils.log(f'[LOC{config.loc.id}] {fn.__name__}: {type(e).__name__} {e}', 3)
	if cachefile:
		setupdated(cachefile)
