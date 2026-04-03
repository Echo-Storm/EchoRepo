# -*- coding: utf-8 -*-
"""
NFL Rewind UI Handlers for plugin.video.echosports

Displays NFL game replays in Kodi.
"""

import sys
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode, quote_plus

from lib.sources.nfl_source import NFLContentSource


def get_fanart(addon):
    """Get default fanart."""
    return addon.getAddonInfo('fanart')


def build_url(base, **kwargs):
    """Build plugin URL with parameters."""
    return base + '?' + urlencode(kwargs)


def build_play_url(link_obj):
    """Build a playable URL that routes through our resolver."""
    base_url = sys.argv[0]
    url = link_obj.get('url', '')
    
    params = {
        'action': 'play_nfl',
        'url': url,
    }
    return f"{base_url}?{urlencode(params)}"


def add_directory_item(plugin_handle, title, action, params, icon, fanart, is_folder=True, plot=''):
    """Add a directory item to the listing."""
    base_url = sys.argv[0]
    url = build_url(base_url, action=action, **params)
    
    li = xbmcgui.ListItem(title)
    li.setArt({
        'thumb': icon,
        'icon': icon,
        'fanart': fanart,
    })
    if plot:
        li.setInfo('video', {'plot': plot})
    
    xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=is_folder)


def add_playable_item(plugin_handle, item, icon, fanart):
    """Add a playable item with potential backup streams."""
    if not item.get('links'):
        return
    
    title = item['title']
    plot = item.get('summary', '')
    thumb = item.get('thumbnail') or icon
    item_fanart = item.get('fanart') or fanart
    
    # Build URL for primary link
    primary_url = build_play_url(item['primary_link'])
    
    li = xbmcgui.ListItem(title)
    li.setArt({
        'thumb': thumb,
        'icon': thumb,
        'fanart': item_fanart,
    })
    li.setInfo('video', {
        'title': title,
        'plot': plot,
        'mediatype': 'video',
    })
    li.setProperty('IsPlayable', 'true')
    
    # Add context menu for backup streams (Full Game, Condensed, etc.)
    if len(item['links']) > 1:
        context_items = []
        for i, link in enumerate(item['links'][1:], start=2):
            label = link.get('label') or f'Stream {i}'
            backup_url = build_play_url(link)
            context_items.append((
                f'Play: {label}',
                f'PlayMedia({backup_url})'
            ))
        li.addContextMenuItems(context_items)
    
    xbmcplugin.addDirectoryItem(plugin_handle, primary_url, li, isFolder=False)


def display_items(plugin_handle, addon, items, category=''):
    """Display a list of formatted items."""
    import xbmc
    
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    
    xbmc.log(f"[NFL] display_items called with {len(items)} raw items", xbmc.LOGINFO)
    
    source = NFLContentSource()
    formatted = source.format_items(items, category)
    
    xbmc.log(f"[NFL] Formatted to {len(formatted)} items", xbmc.LOGINFO)
    
    if not formatted:
        xbmcgui.Dialog().notification('Echo Sports', 'No NFL content found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(plugin_handle, succeeded=False)
        return
    
    for item in formatted:
        if item['type'] == 'dir':
            # Directory item - navigate to XML URL
            if item.get('xml_url'):
                xbmc.log(f"[NFL] Adding dir: {item['title'][:40]}", xbmc.LOGDEBUG)
                add_directory_item(
                    plugin_handle,
                    item['title'],
                    'nfl_fetch_xml',
                    {'xml_url': quote_plus(item['xml_url'])},
                    item.get('thumbnail') or icon,
                    item.get('fanart') or fanart,
                    is_folder=True,
                    plot=item.get('summary', '')
                )
        elif item['type'] == 'item' and item.get('links'):
            # Playable item
            xbmc.log(f"[NFL] Adding item: {item['title'][:40]}", xbmc.LOGDEBUG)
            add_playable_item(plugin_handle, item, icon, fanart)
    
    xbmcplugin.setContent(plugin_handle, 'videos')
    xbmcplugin.endOfDirectory(plugin_handle)


# === Root Menu ===

def show_nfl_root(plugin_handle, addon):
    """
    Show NFL Rewind root menu.
    
    Categories:
    - Current Season (25/26)
    - 24/25 Season
    - 23/24 Season
    """
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    
    # Use NFL-specific icon if available
    nfl_icon = NFLContentSource.DEFAULT_ICON
    nfl_fanart = NFLContentSource.DEFAULT_FANART
    
    categories = [
        {
            'title': '[COLOR lime]25/26 Season (Current)[/COLOR]',
            'action': 'nfl_season_25',
            'plot': 'Full & Condensed game replays from the 25/26 NFL Season',
        },
        {
            'title': '24/25 Season',
            'action': 'nfl_season_24',
            'plot': 'Full & Condensed game replays from the 24/25 NFL Season',
        },
        {
            'title': '23/24 Season',
            'action': 'nfl_season_23',
            'plot': 'Full & Condensed game replays from the 23/24 NFL Season',
        },
    ]
    
    for cat in categories:
        add_directory_item(
            plugin_handle,
            cat['title'],
            cat['action'],
            {},
            nfl_icon,
            nfl_fanart,
            is_folder=True,
            plot=cat.get('plot', '')
        )
    
    xbmcplugin.endOfDirectory(plugin_handle)


# === Season Menus ===

def show_nfl_season_25(plugin_handle, addon):
    """Show 25/26 season menu (weeks + playoffs)."""
    import xbmc
    xbmc.log("[NFL] Fetching 25/26 season...", xbmc.LOGINFO)
    source = NFLContentSource()
    items = source.get_current_season()
    xbmc.log(f"[NFL] Got {len(items)} items from feed", xbmc.LOGINFO)
    display_items(plugin_handle, addon, items, '25/26 Season')


def show_nfl_season_24(plugin_handle, addon):
    """Show 24/25 season menu."""
    source = NFLContentSource()
    items = source.get_season_24()
    display_items(plugin_handle, addon, items, '24/25 Season')


def show_nfl_season_23(plugin_handle, addon):
    """Show 23/24 season menu."""
    source = NFLContentSource()
    items = source.get_season_23()
    display_items(plugin_handle, addon, items, '23/24 Season')


# === Playoff Sections (direct access) ===

def show_nfl_superbowl(plugin_handle, addon):
    """Show Super Bowl games."""
    source = NFLContentSource()
    items = source.get_superbowl()
    display_items(plugin_handle, addon, items, 'Super Bowl')


def show_nfl_probowl(plugin_handle, addon):
    """Show Pro Bowl games."""
    source = NFLContentSource()
    items = source.get_probowl()
    display_items(plugin_handle, addon, items, 'Pro Bowl')


def show_nfl_conference(plugin_handle, addon):
    """Show Conference Championship games."""
    source = NFLContentSource()
    items = source.get_conference()
    display_items(plugin_handle, addon, items, 'Conference Championships')


def show_nfl_divisional(plugin_handle, addon):
    """Show Divisional Round games."""
    source = NFLContentSource()
    items = source.get_divisional()
    display_items(plugin_handle, addon, items, 'Divisional Round')


def show_nfl_wildcard(plugin_handle, addon):
    """Show Wildcard Round games."""
    source = NFLContentSource()
    items = source.get_wildcard()
    display_items(plugin_handle, addon, items, 'Wildcard Round')


# === Dynamic URL Fetch ===

def show_nfl_from_url(plugin_handle, addon, xml_url):
    """
    Fetch and display content from any XML URL.
    Used for nested navigation (weeks, specific games, etc.).
    """
    if not xml_url:
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    source = NFLContentSource()
    items = source.get_content_from_url(xml_url)
    
    if not items:
        xbmcgui.Dialog().notification('Echo Sports', 'No content found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(plugin_handle, succeeded=False)
        return
    
    display_items(plugin_handle, addon, items, 'NFL')
