#
#       Copyright (C) 2014-
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


import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import os, sys

from utils import HOME


# Menu item action codes
_ADDTOFAVES  = 100
_SF_SETTINGS = 200
_SETTINGS    = 250
_STD_MENU    = 0


try:
    import utils
    utils.log("***module capture called")
    ADDON   = utils.ADDON
    ADDONID = utils.ADDONID
    ROOT    = utils.ROOT
    GETTEXT = utils.GETTEXT
    MENU_ADDTOFAVES     = ADDON.getSetting('MENU_ADDTOFAVES')     == 'true'
    MENU_SF_SETTINGS    = ADDON.getSetting('MENU_SF_SETTINGS')    == 'true'
    MENU_ADDON_SETTINGS = ADDON.getSetting('MENU_ADDON_SETTINGS') == 'true'
    MENU_STD_MENU       = ADDON.getSetting('MENU_STD_MENU')       == 'true'
except Exception as e:
    try:    utils.log('Error initialising global menu : %s' % str(e))
    except: xbmc.log('Super Favourites - Error initialising global menu : %s' % str(e), xbmc.LOGERROR)
    ADDON = None


def activateWindow(window):
    xbmc.executebuiltin('Dialog.Close(all, true)')
    xbmc.executebuiltin('ActivateWindow(%s)' % window)


def doStandard(useScript=True):
    window = xbmcgui.getCurrentWindowId()

    if window == 10000:  # home
        if xbmc.getCondVisibility('Window.IsActive(favourites)') != 1:
            return

    if window == 12005:  # video playing
        return activateWindow('videoplaylist')

    if useScript:
        path   = utils.HOME
        script = os.path.join(path, 'standardMenu.py')
        cmd    = 'AlarmClock(%s,RunScript(%s),%d,True)' % ('menu', script, 0)
        xbmc.executebuiltin(cmd)
    else:
        xbmc.executebuiltin('Action(ContextMenu)')


def whitelisted():
    filename = xbmc.getInfoLabel('ListItem.FilenameAndPath')
    try:
        addon = filename.split('://', 1)[-1].split('/', 1)[0]
        if xbmc.getCondVisibility('System.HasAddon(%s)' % addon) == 1:
            addon = xbmcaddon.Addon(addon).getAddonInfo('path')
            addon = addon.rsplit(os.path.sep, 1)[-1]
            return addon in ADDON.getSetting('WHITELIST')
    except:
        pass
    return False


def doMenu(mode):
    import menuUtils

    utils.log('**** Context Menu Information ****')

    window = xbmcgui.getCurrentWindowId()

    DEBUG = ADDON.getSetting('DEBUG') == 'true'
    if DEBUG:
        utils.DialogOK('Current Window ID %d' % window)

    utils.log('Capture window\t: %d' % window)

    if window > 12999:
        doStandard(useScript=False)
        return

    if mode == 0 and ADDON.getSetting('CONTEXT') != 'true':
        doStandard(useScript=False)
        return

    folder = xbmc.getInfoLabel('Container.FolderPath')
    path   = xbmc.getInfoLabel('ListItem.FolderPath')

    # Don't intercept within Super Favourites itself
    if (ADDONID in folder) or (ADDONID in path):
        doStandard(useScript=False)
        return

    if mode == 0 and whitelisted():
        doStandard(useScript=False)
        return

    try:    params = menuUtils.getCurrentParams()
    except: params = None

    if params is None:
        doStandard(useScript=False)
        return

    utils.outputDict(params, 'Capture Parameters')

    path      = params['path']
    label     = params['label']
    thumb     = params['thumb']
    fanart    = params['fanart']
    window    = params['window']

    choice    = 0
    menu      = []
    localAddon = None

    if len(path) > 0:
        if MENU_ADDTOFAVES:
            menu.append((GETTEXT(30047), _ADDTOFAVES))  # "Add to Super Favourites"

        if MENU_ADDON_SETTINGS:
            localAddon = utils.findAddon(path)
            if localAddon:
                name = utils.getSettingsLabel(localAddon)
                menu.append((name, _SETTINGS))

    if MENU_SF_SETTINGS:
        menu.append((GETTEXT(30049), _SF_SETTINGS))  # "Super Favourites settings"

    stdMenu = False
    if MENU_STD_MENU:
        if (len(path) > 0) or (window == 10034):
            stdMenu = True
            menu.append((GETTEXT(30048), _STD_MENU))  # "Standard context menu"

    if len(menu) == 0 or (len(menu) == 1 and stdMenu):
        doStandard(useScript=False)
        return

    xbmcgui.Window(10000).setProperty('SF_MENU_VISIBLE', 'true')

    dialog = ADDON.getSetting('CONTEXT_STYLE') == '1'

    import menus

    if dialog:
        choice = menus.selectMenu(utils.TITLE, menu)
    else:
        choice = menus.showMenu(ADDONID, menu, useBuiltin=False)

    utils.log('selection\t\t: %s' % choice)

    if choice == _STD_MENU:
        doStandard(useScript=True)

    if choice == _SF_SETTINGS:
        utils.ADDON.openSettings()

    if choice == _SETTINGS:
        xbmcaddon.Addon(localAddon).openSettings()

    if choice == _ADDTOFAVES:
        try:
            meta = menuUtils.getCurrentMeta()
        except:
            meta = {}
        menuUtils.addToFaves(params, meta)


def menu(mode):
    if xbmcgui.Window(10000).getProperty('SF_MENU_VISIBLE') == 'true':
        return

    if ADDON.getSetting('MENU_MSG') == 'true':
        ADDON.setSetting('MENU_MSG', 'false')
        if utils.DialogYesNo(GETTEXT(35015), GETTEXT(35016), GETTEXT(35017)):
            utils.openSettings(ADDONID, 2.6)
            return

    doMenu(mode)


def main():
    if xbmc.getCondVisibility('Window.IsActive(favourites)') == 1:
        return doStandard(useScript=False)

    mode = 0

    if len(sys.argv) > 0:
        if sys.argv[0] == '':
            mode = 1  # launched via std context menu
        if sys.argv[-1].lower() == 'launchsfmenu':
            mode = 2  # launched via LaunchSFMenu script

    try:
        menu(mode)
    except Exception as e:
        utils.log('Exception in capture.py %s' % str(e))
        doStandard(useScript=False)


progress = xbmc.getCondVisibility('Window.IsActive(progressdialog)') == 1
if ADDON and not progress:
    main()
    xbmc.sleep(1000)
    xbmcgui.Window(10000).clearProperty('SF_MENU_VISIBLE')
else:
    xbmc.executebuiltin('Action(ContextMenu)')
