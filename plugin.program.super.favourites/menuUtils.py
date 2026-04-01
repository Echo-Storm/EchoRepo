#
#       Copyright (C) 2016-
#       Sean Poyser (seanpoyser@gmail.com)
#       Portions Copyright (c) 2020 John Moore
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#

import xbmc, xbmcgui, xbmcvfs

import favourite
import utils
from utils import ADDONID

GETTEXT = utils.GETTEXT
ADDON   = utils.ADDON


def getText(title, text=''):
    if text is None:
        text = ''
    kb = xbmc.Keyboard(text.strip(), title)
    kb.doModal()
    if not kb.isConfirmed():
        return None
    text = kb.getText().strip()
    if len(text) < 1:
        return None
    return text


def getPrefix():
    try:    return 'Container(%d).' % int(xbmc.getInfoLabel('System.CurrentControlId'))
    except: return ''


def fixWindowID(window):
    if window not in [10000, 11100]:
        return window

    if not utils.ESTUARY_SKIN:
        return 10025  # fallback to video

    try:    id = int(xbmc.getInfoLabel('System.CurrentControlId'))
    except: id = 0

    if id in [8100, 50050]:  # video
        return 10025
    if id in [8200, 50150]:  # music
        return 10502
    if id in [8300, 50250]:  # programs
        return 10001
    if id in [8500, 50350]:  # pictures
        return 10002

    return 10025  # fallback to video


def getCmd(path, fanart, desc, window, filename, isFolder, meta, picture):
    cmd = _getCmd(path, fanart, desc, window, filename, isFolder, meta, picture)
    return favourite.fixCase(cmd)


def _getCmd(path, fanart, desc, window, filename, isFolder, meta, picture):
    if path.lower().startswith('addons://user/'):
        path     = path.replace('addons://user/', 'plugin://')
        isFolder = True
        window   = 10025

    window = fixWindowID(window)

    if window == 10003:  # FileManager
        import sfile
        import os

        isFolder = sfile.isdir(path)
        if isFolder:
            if path.startswith('special://'):
                path = xbmcvfs.translatePath(path)
            path = path.replace('%s%s' % (os.sep, os.sep), os.sep)
            path = path.replace(os.sep, '/')
            folder = path
            if folder.endswith('/'):
                folder = folder[:-1]
            folder = folder.rsplit('/', 1)[-1]
        else:
            if not sfile.isfile(path):
                return None

    if favourite.isKodiCommand(path):
        return path
    elif len(picture) > 0:
        cmd = 'ShowPicture("%s")' % picture
    elif isFolder:
        cmd = 'ActivateWindow(%d,"%s' % (window, path)
    elif path.lower().startswith('script'):
        cmd = 'RunScript("%s' % path.replace('script://', '')
    elif path.lower().startswith('videodb') and len(filename) > 0:
        cmd = 'PlayMedia("%s' % filename.replace('\\', '\\\\')
    elif path.lower().startswith('androidapp'):
        cmd = 'StartAndroidActivity("%s")' % path.replace('androidapp://sources/apps/', '', 1)
    else:
        utils.log('***else clause: cmd = \'PlayMedia("%s")\' % path')
        cmd = 'PlayMedia("%s")' % path
        cmd = favourite.updateSFOption(cmd, 'winID', window)

    cmd = favourite.addFanart(cmd, fanart)
    cmd = favourite.updateSFOption(cmd, 'desc', desc)

    if meta:
        from urllib.parse import quote_plus
        meta = utils.convertDictToURL(meta)
        cmd  = favourite.updateSFOption(cmd, 'meta', quote_plus(meta))

    if isFolder:
        cmd = cmd.replace('")', '",return)')

    return cmd


def copyFave(name, thumb, cmd):
    import os
    text = GETTEXT(30019)

    folder = utils.GetSFFolder(text)
    if not folder:
        return False

    file = os.path.join(folder, utils.FILENAME)

    if ADDON.getSetting('MENU_EDITFAVE') == 'true':
        name = getText(GETTEXT(30021), name)

    if not name:
        return False

    fave = [name, thumb, cmd]

    return favourite.copyFave(file, fave)


def getDescription():
    prefix = getPrefix()

    labels = [
        '%sListItem.Plot'                             % prefix,
        '%sListItem.AddonDescription'                 % prefix,
        '%sListItem.AddonSummary'                     % prefix,
        '%sListItem.Property(Artist_Description)'     % prefix,
        '%sListItem.Property(Album_Description)'      % prefix,
        '%sListItem.Artist'                           % prefix,
        '%sListItem.Comment'                          % prefix,
    ]

    for label in labels:
        desc = xbmc.getInfoLabel(label)
        if len(desc) > 0:
            return desc

    return ''


def addToFaves(params, meta=None):
    try:
        label    = params['label']
        thumb    = params['thumb']
        fanart   = params['fanart']
        path     = params['path']
        desc     = params['description']
        window   = params['window']
        filename = params['filename']
        isFolder = params['isfolder']
        picture  = params['picture']

        cmd = getCmd(path, fanart, desc, window, filename, isFolder, meta, picture)

        if cmd:
            copyFave(label, thumb, cmd)
    except Exception as e:
        utils.log('\n\nError in menuUtils.addToFaves : %s' % str(e))
        utils.outputDict(params)


def getCurrentMeta():
    """Collect video/audio metadata from the currently highlighted list item."""
    infoLabels = [
        'rating', 'userrating', 'votes', 'trailer', 'duration',
        'genre', 'mpaa', 'plot', 'plotoutline', 'tagline',
        'title', 'originaltitle', 'writer', 'director',
        'year', 'premiered', 'season', 'episode', 'imdbnumber', 'studio',
    ]

    prefix = getPrefix()
    params = {}

    for label in infoLabels:
        value = xbmc.getInfoLabel('%sListItem.%s' % (prefix, label))
        if value:
            if label == 'duration':
                try:    value = int(value) * 60
                except: continue
            params[label] = value

    return params


def getCurrentParams():
    prefix = getPrefix()

    window   = xbmcgui.getCurrentWindowId()
    path     = xbmc.getInfoLabel('%sListItem.FolderPath' % prefix)
    label    = xbmc.getInfoLabel('%sListItem.Label' % prefix)
    filename = xbmc.getInfoLabel('%sListItem.FilenameAndPath' % prefix)
    thumb    = xbmc.getInfoLabel('%sListItem.Thumb' % prefix)
    icon     = xbmc.getInfoLabel('%sListItem.ActualIcon' % prefix)
    playable = xbmc.getInfoLabel('%sListItem.Property(IsPlayable)' % prefix).lower() == 'true'
    fanart   = xbmc.getInfoLabel('%sListItem.Art(fanart)' % prefix)
    isFolder = xbmc.getCondVisibility('%sListItem.IsFolder' % prefix) == 1
    picture  = xbmc.getInfoLabel('%sListItem.PicturePath' % prefix)

    desc = getDescription()

    if not thumb:
        thumb = icon

    try:    file = xbmc.Player().getPlayingFile()
    except: file = None

    isStream = xbmc.getCondVisibility('Player.IsInternetStream') == 1

    if window == 10003:  # filemanager
        try:    id = int(xbmc.getInfoLabel('System.CurrentControlId'))
        except: id = 0

        if id not in [20, 21]:
            return None

        import os
        if path.endswith(os.sep):
            path = path[:-1]

        isFolder = True
        thumb    = 'DefaultFolder.png'

    if isFolder:
        path     = path.replace('\\', '\\\\')
        filename = filename.replace('\\', '\\\\')

    params                = {}
    params['label']       = label
    params['path']        = path
    params['filename']    = filename
    params['thumb']       = thumb
    params['icon']        = icon
    params['fanart']      = fanart
    params['window']      = window
    params['isplayable']  = playable
    params['isfolder']    = isFolder
    params['file']        = file
    params['isstream']    = isStream
    params['description'] = desc
    params['picture']     = picture

    return params
