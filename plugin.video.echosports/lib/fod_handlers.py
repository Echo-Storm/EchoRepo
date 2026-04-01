# -*- coding: utf-8 -*-
"""
Fights on Demand (FOD) UI Handlers for plugin.video.echosports

Displays UFC, MMA, and Boxing content in Kodi.
"""

import sys
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode, quote_plus

from lib.sources.fod_comprehensive import FODContentSource


def get_addon_path(addon):
    """Get addon path for resources."""
    return addon.getAddonInfo('path')


def get_fanart(addon):
    """Get default fanart."""
    return addon.getAddonInfo('fanart')


def build_url(base, **kwargs):
    """Build plugin URL with parameters."""
    return base + '?' + urlencode(kwargs)


def build_play_url(link_obj):
    """
    Build a playable URL that routes through our resolver.
    """
    base_url = sys.argv[0]
    url = link_obj.get('url', '')
    
    params = {
        'action': 'play_fod',
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
    
    # Add context menu for backup streams
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
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    base_url = sys.argv[0]
    
    source = FODContentSource()
    formatted = source.format_items(items, category)
    
    for item in formatted:
        if item['type'] == 'dir':
            # Directory item - navigate to XML URL
            if item.get('xml_url'):
                add_directory_item(
                    plugin_handle,
                    item['title'],
                    'fod_fetch_xml',
                    {'xml_url': quote_plus(item['xml_url'])},
                    item.get('thumbnail') or icon,
                    item.get('fanart') or fanart,
                    is_folder=True,
                    plot=item.get('summary', '')
                )
        elif item['type'] == 'item' and item.get('links'):
            # Playable item
            add_playable_item(plugin_handle, item, icon, fanart)
    
    xbmcplugin.setContent(plugin_handle, 'videos')
    xbmcplugin.endOfDirectory(plugin_handle)


# === Root Menu ===

def show_fod_root(plugin_handle, addon):
    """
    Show FOD root menu.
    
    Categories:
    - Latest UFC/MMA
    - UFC Events
    - MMA Events  
    - Boxing
    - Free (Non-Debrid)
    """
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    
    categories = [
        {
            'title': '[COLOR lime]Latest UFC/MMA[/COLOR]',
            'action': 'fod_latest',
            'plot': 'Latest UFC and MMA event replays',
        },
        {
            'title': 'UFC Events',
            'action': 'fod_ufc',
            'plot': 'UFC PPV, Fight Night, ESPN, ABC, and classic events',
        },
        {
            'title': 'MMA Events',
            'action': 'fod_mma',
            'plot': 'MMA events from various promotions (ONE, Bellator, PFL, etc.)',
        },
        {
            'title': 'Boxing',
            'action': 'fod_boxing',
            'plot': 'Boxing event replays',
        },
        {
            'title': '[COLOR cyan]Free (No Debrid)[/COLOR]',
            'action': 'fod_free',
            'plot': 'Content that does not require a debrid account',
        },
    ]
    
    for cat in categories:
        add_directory_item(
            plugin_handle,
            cat['title'],
            cat['action'],
            {},
            icon,
            fanart,
            is_folder=True,
            plot=cat.get('plot', '')
        )
    
    xbmcplugin.endOfDirectory(plugin_handle)


# === Latest Content ===

def show_fod_latest(plugin_handle, addon):
    """Show latest UFC/MMA events."""
    source = FODContentSource()
    items = source.get_latest_ufc_mma()
    display_items(plugin_handle, addon, items, 'Latest UFC/MMA')


# === UFC Sections ===

def show_fod_ufc_menu(plugin_handle, addon):
    """Show UFC events submenu."""
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    
    categories = [
        {'title': 'UFC PPV', 'action': 'fod_ufc_ppv', 'plot': 'UFC Pay-Per-View events'},
        {'title': 'UFC Fight Night', 'action': 'fod_ufc_fight_night', 'plot': 'UFC Fight Night events'},
        {'title': 'UFC on ESPN', 'action': 'fod_ufc_espn', 'plot': 'UFC on ESPN events'},
        {'title': 'UFC on ABC', 'action': 'fod_ufc_abc', 'plot': 'UFC on ABC events'},
        {'title': 'UFC BJJ', 'action': 'fod_ufc_bjj', 'plot': 'UFC BJJ events'},
        {'title': 'UFC Shows & Series', 'action': 'fod_ufc_shows', 'plot': 'UFC shows and series'},
        {'title': '[COLOR gray]Classic UFC PPV[/COLOR]', 'action': 'fod_ufc_classic_ppv', 'plot': 'Classic UFC PPV events'},
        {'title': '[COLOR gray]Classic UFC Fight Night[/COLOR]', 'action': 'fod_ufc_classic_fn', 'plot': 'Classic UFC Fight Night events'},
    ]
    
    for cat in categories:
        add_directory_item(
            plugin_handle,
            cat['title'],
            cat['action'],
            {},
            icon,
            fanart,
            is_folder=True,
            plot=cat.get('plot', '')
        )
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_fod_ufc_ppv(plugin_handle, addon):
    """Show UFC PPV events."""
    source = FODContentSource()
    items = source.get_ufc_ppv()
    display_items(plugin_handle, addon, items, 'UFC PPV')


def show_fod_ufc_fight_night(plugin_handle, addon):
    """Show UFC Fight Night events."""
    source = FODContentSource()
    items = source.get_ufc_fight_night()
    display_items(plugin_handle, addon, items, 'UFC Fight Night')


def show_fod_ufc_espn(plugin_handle, addon):
    """Show UFC on ESPN events."""
    source = FODContentSource()
    items = source.get_ufc_espn()
    display_items(plugin_handle, addon, items, 'UFC on ESPN')


def show_fod_ufc_abc(plugin_handle, addon):
    """Show UFC on ABC events."""
    source = FODContentSource()
    items = source.get_ufc_abc()
    display_items(plugin_handle, addon, items, 'UFC on ABC')


def show_fod_ufc_bjj(plugin_handle, addon):
    """Show UFC BJJ events."""
    source = FODContentSource()
    items = source.get_ufc_bjj()
    display_items(plugin_handle, addon, items, 'UFC BJJ')


def show_fod_ufc_classic_ppv(plugin_handle, addon):
    """Show Classic UFC PPV events."""
    source = FODContentSource()
    items = source.get_ufc_classic_ppv()
    display_items(plugin_handle, addon, items, 'Classic UFC PPV')


def show_fod_ufc_classic_fn(plugin_handle, addon):
    """Show Classic UFC Fight Night events."""
    source = FODContentSource()
    items = source.get_ufc_classic_fn()
    display_items(plugin_handle, addon, items, 'Classic UFC Fight Night')


def show_fod_ufc_shows(plugin_handle, addon):
    """Show UFC Shows & Series."""
    source = FODContentSource()
    items = source.get_ufc_shows()
    display_items(plugin_handle, addon, items, 'UFC Shows & Series')


# === MMA Section ===

def show_fod_mma(plugin_handle, addon):
    """Show MMA events."""
    source = FODContentSource()
    items = source.get_mma_events()
    display_items(plugin_handle, addon, items, 'MMA Events')


# === Boxing Sections ===

def show_fod_boxing(plugin_handle, addon):
    """Show boxing replays."""
    source = FODContentSource()
    items = source.get_boxing()
    display_items(plugin_handle, addon, items, 'Boxing')


def show_fod_boxing_free(plugin_handle, addon):
    """Show non-debrid boxing replays."""
    source = FODContentSource()
    items = source.get_boxing_nondebrid()
    display_items(plugin_handle, addon, items, 'Boxing (Free)')


# === Free (Non-Debrid) Sections ===

def show_fod_free_menu(plugin_handle, addon):
    """Show free (non-debrid) content menu."""
    icon = addon.getAddonInfo('icon')
    fanart = get_fanart(addon)
    
    categories = [
        {'title': 'UFC (Free)', 'action': 'fod_ufc_free', 'plot': 'UFC replays that do not require debrid'},
        {'title': 'MMA (Free)', 'action': 'fod_mma_free', 'plot': 'MMA replays that do not require debrid'},
        {'title': 'Boxing (Free)', 'action': 'fod_boxing_free', 'plot': 'Boxing replays that do not require debrid'},
    ]
    
    for cat in categories:
        add_directory_item(
            plugin_handle,
            cat['title'],
            cat['action'],
            {},
            icon,
            fanart,
            is_folder=True,
            plot=cat.get('plot', '')
        )
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_fod_ufc_free(plugin_handle, addon):
    """Show non-debrid UFC replays."""
    source = FODContentSource()
    items = source.get_nondebrid_ufc()
    display_items(plugin_handle, addon, items, 'UFC (Free)')


def show_fod_mma_free(plugin_handle, addon):
    """Show non-debrid MMA replays."""
    source = FODContentSource()
    items = source.get_nondebrid_mma()
    display_items(plugin_handle, addon, items, 'MMA (Free)')


# === Dynamic URL Fetch ===

def show_fod_from_url(plugin_handle, addon, xml_url):
    """
    Fetch and display content from any XML URL.
    Used for nested navigation.
    """
    if not xml_url:
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    source = FODContentSource()
    items = source.get_content_from_url(xml_url)
    
    if not items:
        xbmcgui.Dialog().notification('Echo Sports', 'No content found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(plugin_handle, succeeded=False)
        return
    
    display_items(plugin_handle, addon, items, 'FOD')
