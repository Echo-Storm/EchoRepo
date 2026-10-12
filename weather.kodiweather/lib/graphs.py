"""Hourly graph properties: one set of bar images, axis labels, colours and alert flags per measurement.

Moved out of utils.getprop() unchanged (only the indentation moved). Called through getprop for map rows of kind "graph", and only
when the hidden setting enablegraphs is on (no shipped skin reads these properties; the alert checks use their own code in weather.py).
"""
from . import config
from . import conv
from .utils import addprop, index, setting


def build(data, map):
	idxnow    = index("now", data)
	type      = map[2][1]
	unit      = map[4]
	scaleneg  = False
	count     = 1
	property  = f'{map[2][0]}.{count}.{map[2][1]}'
	content   = None
	alerting  = setting(f'alert_{type.split(".")[0]}_enabled', 'bool', True)

	# Guard: index not found (weather data not yet loaded)
	if idxnow is None:
		return content

	# Data
	lv = []
	lt = []

	for idx in range(idxnow, idxnow+24):
		try:
			v = data[map[1][0]][map[1][1]][idx]
			t = data[map[1][0]]['time'][idx]
		except (KeyError, IndexError, TypeError):
			continue
		else:
			lv.append(v)
			lt.append(t)

	# Unit
	lc   = [ conv.item(v, unit, False) for v in lv ]
	unit = conv.item(False, unit)

	addprop(f'{property}.unit', unit)

	# Guard: no usable data for this graph
	if not lc:
		return content

	# Neg
	scaleneg = bool([ v for v in lc if v < 0 ])

	# Scale
	scalemin = min(lc)
	scalemax = max(lc)
	scaleabs = max([ abs(v) for v in lc ])

	r = 1 if scalemin < 1 and scalemax < 1 else None
	a = scalemax/4
	s = (scalemax-scalemin)/4

	addprop(f'{property}.xaxis0', round(scalemax,r))
	addprop(f'{property}.xaxis1', round(scalemax-a,r))
	addprop(f'{property}.xaxis2', round(scalemax-a*2,r))
	addprop(f'{property}.xaxis3', round(scalemax-a*3,r))
	addprop(f'{property}.xaxis4', round(scalemax-a*4,r))

	addprop(f'{property}.scalexaxis0', round(scalemax,r))
	addprop(f'{property}.scalexaxis1', round(scalemax-s,r))
	addprop(f'{property}.scalexaxis2', round(scalemax-s*2,r))
	addprop(f'{property}.scalexaxis3', round(scalemax-s*3,r))
	addprop(f'{property}.scalexaxis4', round(scalemax-s*4,r))

	# Graph
	for idx in range(0,24):
		alert     = 0
		property  = f'{map[2][0]}.{count}.{map[2][1]}'

		try:
			time   = lt[idx]
			avalue = lv[idx]
			value  = lc[idx]

		except (KeyError, IndexError, TypeError):
			continue
		else:
			negative = True if value < 0 else False

			if scalemax-scalemin == 0 or scaleabs == 0:
				percent = 0
			else:
				percent = round((value-scalemin)/(scalemax-scalemin)*100) if not negative else round(abs(value)/scaleabs*100)

			if scalemax == 0 or scaleabs == 0:
				percentabs = 0
			else:
				percentabs = round((value)/(scalemax)*100) if not negative else round(abs(value)/scaleabs*100)

			# Time
			addprop(f'{property}.time', conv.time('hour', time))

			# Value
			addprop(f'{property}.value', value)

			# Image
			if scaleneg:
				if negative:
					addprop(f'{property}.image', f'{config.addon_icons}/graph/{config.kodi.height}/bar_n{percent}n.png')
					addprop(f'{property}.code', f'n{percent}n')
				else:
					addprop(f'{property}.image', f'{config.addon_icons}/graph/{config.kodi.height}/bar_n{percent}p.png')
					addprop(f'{property}.code', f'n{percent}p')

			else:
				addprop(f'{property}.image', f'{config.addon_icons}/graph/{config.kodi.height}/bar_{percentabs}p.png')
				addprop(f'{property}.code', f'{percentabs}p')
				addprop(f'{property}.scaleimage', f'{config.addon_icons}/graph/{config.kodi.height}/bar_{percent}p.png')
				addprop(f'{property}.scalecode', f'{percent}p')

			# Alert
			if alerting:

				for c, d in [(x, y) for x in [ 3, 2, 1 ] for y in [ 'high', 'low', 'wmo' ] ]:
					last =  False

					try:
						if d == 'wmo':
							limit = list(config.alert.map[type][f'alert_{type.split(".")[0]}_{d}_{c}'].split(' '))
						else:
							limit = int(config.alert.map[type][f'alert_{type.split(".")[0]}_{d}_{c}'])
					except (KeyError, ValueError, TypeError, AttributeError):
						continue

					if d == 'high':
						if avalue >= limit:
							if last and avalue > last:
								alert, last = c, avalue
							elif not last:
								alert, last = c, avalue
					elif d == 'low':
						if avalue <= limit:
							if last and avalue < last:
								alert, last = c, avalue
							elif not last:
								alert, last = c, avalue
					elif d == 'wmo':
						for wmo in limit:
							if avalue == int(wmo):
								if last and avalue > last:
									alert, last = c, avalue
								elif not last:
									alert, last = c, avalue
					if alert:
						break

			addprop(f'{property}.alert', alert)

			# Alert icon
			if alert == 0:
				addprop(f'{property}.alerticon', '')
			else:
				if type == 'condition.graph':
					icon  = f'{config.map_alert_condition.get(last)}{alert}'
					addprop(f'{property}.alerticon', f'{config.addon_icons}/alert/{icon}.png')
				else:
					addprop(f'{property}.alerticon', f'{config.addon_icons}/alert/{config.alert.map[type]["icon"]}{alert}.png')

			# Color
			if alert == 0:
				if negative:
					addprop(f'{property}.color', config.addon.cnegative)
					addprop(f'{property}.colornormal', config.addon.cnegative)
				else:
					addprop(f'{property}.color', config.addon.cdefault)
					addprop(f'{property}.colornormal', config.addon.cnormal)

			elif alert == 1:
				addprop(f'{property}.color', config.addon.cnotice)
				addprop(f'{property}.colornormal', config.addon.cnotice)

			elif alert == 2:
				addprop(f'{property}.color', config.addon.ccaution)
				addprop(f'{property}.colornormal', config.addon.ccaution)

			elif alert == 3:
				addprop(f'{property}.color', config.addon.cdanger)
				addprop(f'{property}.colornormal', config.addon.cdanger)

			count += 1

	return content
