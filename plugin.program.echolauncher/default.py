import json
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

import store

ADDON = xbmcaddon.Addon()
ID = ADDON.getAddonInfo('id')
URL = f'plugin://{ID}/'
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
PARAMS = dict(parse_qsl(sys.argv[2].lstrip('?'))) if len(sys.argv) > 2 else {}


def limit():
	"""Most entries a shelf may hold (setting 'limit'; the add-on refuses more when adding, it never hides entries that are already there)."""
	try:
		return max(1, int(ADDON.getSetting('limit') or 5))
	except ValueError:
		return 5


def text(number, *args):
	return ADDON.getLocalizedString(number).format(*args)


def link(**query):
	return f'{URL}?{urlencode(query)}'


def info(addon_id):
	"""The installed add-on, or None (not installed / disabled: the entry is hidden, as it would be an empty click)."""
	try:
		return xbmcaddon.Addon(addon_id)
	except RuntimeError:
		return None


def add_item(label, target, folder, art=None, plot='', menu=None):
	li = xbmcgui.ListItem(label, offscreen=True)
	if art:
		li.setArt(art)
	if plot:
		li.getVideoInfoTag().setPlot(plot)
	if menu:
		li.addContextMenuItems(menu)
	xbmcplugin.addDirectoryItem(HANDLE, target, li, folder)


def show_groups():
	for group in store.load():
		add_item(group, link(group=group, manage=1), True)
	xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def show_group(group, manage):
	"""One shelf. Each entry is a folder item that points straight at the add-on, so a click needs no code of ours.
	`manage` is set only when the shelf is opened from this add-on's own list (never from a widget): then the entries get the
	Remove / Move menu, the 'Add add-ons' item appears, and entries whose add-on is gone are shown (marked) so they can be removed.
	A widget shows only what can be opened and offers no editing, so nothing can be changed by a stray key press on the home screen."""
	entries = store.load().get(group, [])
	for index, entry in enumerate(entries):
		addon = info(entry['id'])
		if not addon and not manage:
			continue
		menu = None
		if manage:
			args = dict(group=group, index=index, id=entry['id'])
			menu = [(text(32003, group), 'RunPlugin(' + link(action='remove', **args) + ')')]
			if index > 0:
				menu.append((text(32004), 'RunPlugin(' + link(action='move', by=-1, **args) + ')'))
			if index < len(entries) - 1:
				menu.append((text(32005), 'RunPlugin(' + link(action='move', by=1, **args) + ')'))
		label = entry.get('label') or (addon.getAddonInfo('name') if addon else entry['id'])
		if not addon:
			add_item(f"{label} ({text(32010)})", link(action='missing'), False, menu=menu)
			continue
		# No fanart on purpose: Silvo shows the focused widget item's fanart as the home background, and the owner wants the menu item's
		# (conditional weather) background to stay while a tile is highlighted.
		icon = addon.getAddonInfo('icon')
		add_item(label, entry.get('url') or f"plugin://{entry['id']}/", True,
		         art={'thumb': icon, 'icon': icon}, plot=entry.get('desc', ''), menu=menu)
	if manage:
		add_item(f'{text(32001)} ({len(entries)}/{limit()})', link(action='add', group=group), False, art={'icon': 'DefaultAddSource.png', 'thumb': 'DefaultAddSource.png'})
	xbmcplugin.setContent(HANDLE, 'files')
	xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def installed_plugins():
	reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddons', 'params': {
		'type': 'xbmc.python.pluginsource', 'enabled': True, 'properties': ['name', 'summary', 'thumbnail']}})))
	found = reply.get('result', {}).get('addons', [])
	return sorted((a for a in found if a['addonid'] != ID), key=lambda a: a['name'].lower())


def add(group):
	data = store.load()
	have = {entry['id'] for entry in data.get(group, [])}
	room = limit() - len(data.get(group, []))
	if room <= 0:
		xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), text(32012, group, limit()))
		return
	choices = [a for a in installed_plugins() if a['addonid'] not in have]
	if not choices:
		xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), text(32006, group), xbmcgui.NOTIFICATION_INFO)
		return
	rows = []
	for a in choices:
		li = xbmcgui.ListItem(a['name'], a.get('summary', ''), offscreen=True)
		li.setArt({'icon': a.get('thumbnail', '')})
		rows.append(li)
	while True:
		picked = xbmcgui.Dialog().multiselect(text(32002, group) + f' ({room})', rows, useDetails=True)
		if not picked:
			return
		if len(picked) <= room:
			break
		xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), text(32013, room, group))
	for i in picked:
		data.setdefault(group, []).append({'id': choices[i]['addonid'], 'label': choices[i]['name'], 'desc': choices[i].get('summary', '')})
	store.save(data)
	xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), text(32007, ', '.join(choices[i]['name'] for i in picked)), xbmcgui.NOTIFICATION_INFO)
	xbmc.executebuiltin('Container.Refresh')


def remove(group, index, addon_id):
	data = store.load()
	entries = data.get(group, [])
	if 0 <= index < len(entries) and entries[index]['id'] == addon_id:
		name = entries[index].get('label') or addon_id
		if not xbmcgui.Dialog().yesno(ADDON.getAddonInfo('name'), text(32009, name, group)):
			return
		gone = entries.pop(index)
		store.save(data)
		xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), text(32008, gone.get('label') or addon_id), xbmcgui.NOTIFICATION_INFO)
		xbmc.executebuiltin('Container.Refresh')


def move(group, index, addon_id, by):
	data = store.load()
	entries = data.get(group, [])
	target = index + by
	if 0 <= index < len(entries) and 0 <= target < len(entries) and entries[index]['id'] == addon_id:
		entries[index], entries[target] = entries[target], entries[index]
		store.save(data)
		xbmc.executebuiltin('Container.Refresh')


def number(key, default=-1):
	try:
		return int(PARAMS.get(key, default))
	except ValueError:
		return default


def route():
	action = PARAMS.get('action')
	group = PARAMS.get('group')
	if action == 'add':
		add(group)
	elif action == 'remove':
		remove(group, number('index'), PARAMS.get('id'))
	elif action == 'move':
		move(group, number('index'), PARAMS.get('id'), number('by', 0))
	elif action == 'missing':
		xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), text(32011))
	elif group:
		show_group(group, PARAMS.get('manage') == '1')
	else:
		show_groups()


if (__name__ == '__main__'):
	route()
