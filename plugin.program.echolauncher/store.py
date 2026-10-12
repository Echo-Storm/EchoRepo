import json
import os
import shutil

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
FOLDER = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
FILE = os.path.join(FOLDER, 'launchers.json')
DEFAULT_GROUPS = ('Video', 'Stream')


def _read(path):
	with open(path, encoding='utf-8') as f:
		data = json.load(f)
	if not isinstance(data, dict):
		raise ValueError('not a dict')
	return data


def load():
	"""{group: [entry, ...]} in the order of the file; an entry is {'id': add-on id, 'label': ..., 'desc': ..., 'url': optional plugin:// URL}.
	A damaged file falls back to the copy made before the last save, then to empty default shelves."""
	for path in (FILE, FILE + '.bak'):
		try:
			data = _read(path)
		except (OSError, ValueError):
			continue
		if data:
			break
	else:
		data = {}
	for name in DEFAULT_GROUPS:        # the standard shelves always exist, so an older file gets the new ones
		data.setdefault(name, [])
	return data


def save(data):
	os.makedirs(FOLDER, exist_ok=True)
	if os.path.exists(FILE):
		try:
			_read(FILE)
			shutil.copyfile(FILE, FILE + '.bak')       # only a file that still reads correctly becomes the copy
		except (OSError, ValueError):
			pass
	tmp = FILE + '.tmp'
	with open(tmp, 'w', encoding='utf-8') as f:
		json.dump(data, f, indent=1, ensure_ascii=False)
	os.replace(tmp, FILE)
