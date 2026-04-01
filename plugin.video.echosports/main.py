# -*- coding: utf-8 -*-
"""
Echo Sports - Main Entry Point
Private sports addon for Kodi
"""

import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from lib.ui.router import Router


def main():
    """Main entry point for the addon."""
    addon = xbmcaddon.Addon()
    addon_name = addon.getAddonInfo('name')
    addon_version = addon.getAddonInfo('version')
    
    # Log startup
    xbmc.log(f"[{addon_name}] v{addon_version} starting...", xbmc.LOGINFO)
    
    # Parse arguments
    handle = int(sys.argv[1])
    paramstring = sys.argv[2][1:] if len(sys.argv) > 2 else ""
    
    # Route the request
    router = Router(handle)
    router.route(paramstring)


if __name__ == '__main__':
    main()
