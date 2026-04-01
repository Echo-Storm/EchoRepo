"""
Transparent Wrestling Category Handler for plugin.video.echosports

Integrates ALL wrestling content seamlessly with NO extra menus or branding.
Organizes ~1700+ wrestling items into a logical, native-feeling structure.

Content breakdown:
- 9 live 24/7 channels
- 457 WWE RAW episodes  
- 435 WWE SmackDown episodes
- 544 Independent wrestling items
- 82 wrestling movies/TV shows
- Plus AEW, TNA, NWA, NJPW, ROH, PPVs, documentaries, interviews, special matches, archive

Total: ~1700+ items
"""

import xbmcgui
import xbmcplugin
import xbmc
import sys
from urllib.parse import urlencode, quote_plus

# Import the comprehensive wrestling source
from lib.sources.wrestling_comprehensive import WrestlingContentSource


def get_media_path(addon, filename):
    """Get path to media file."""
    return addon.getAddonInfo('path') + f'/resources/media/wrestling/{filename}'


def build_url(base, **kwargs):
    """Build plugin URL with parameters."""
    return base + '?' + urlencode(kwargs)


def build_playable_url(link_obj):
    """
    Build a plugin URL that routes through our resolver.
    This ensures yt-dlp handles sites like mail.ru, dood, etc.
    """
    from urllib.parse import urlencode, quote_plus
    
    raw_url = link_obj['url']
    headers = link_obj.get('headers', {})
    
    # Check if this is already a direct stream (m3u8, mp4 from CDN)
    is_direct = any(x in raw_url.lower() for x in [
        '.m3u8', '.mp4', '.ts',
        'cloudfront.net', 'akamaihd.net', 'pluto.tv',
        'warnermediacdn.com', '.m3u', 'index.m3u8'
    ])
    
    if is_direct:
        # Direct streams can be played as-is with headers
        if headers:
            header_parts = [f'{k}={v}' for k, v in headers.items()]
            return f"{raw_url}|{'&'.join(header_parts)}"
        return raw_url
    else:
        # Route through our play_wrestling action for yt-dlp resolution
        base_url = sys.argv[0]
        params = {
            'action': 'play_wrestling',
            'url': raw_url,
        }
        if headers:
            import json
            params['headers'] = quote_plus(json.dumps(headers))
        return f"{base_url}?{urlencode(params)}"


def build_direct_url(link_obj):
    """Build direct URL with headers (for context menu backup streams)."""
    url = link_obj['url']
    headers = link_obj.get('headers', {})
    
    if headers:
        header_parts = [f'{k}={v}' for k, v in headers.items()]
        url = f"{url}|{'&'.join(header_parts)}"
    
    return url


def add_backup_streams_context(li, links):
    """Add context menu for backup streams."""
    if len(links) > 1:
        from urllib.parse import urlencode, quote_plus
        base_url = sys.argv[0]
        
        context_items = []
        for i, link in enumerate(links[1:], start=2):
            # Route backup streams through resolver too
            params = {
                'action': 'play_wrestling',
                'url': link['url'],
            }
            backup_url = f"{base_url}?{urlencode(params)}"
            context_items.append((
                f'Play Backup Stream {i}',
                f'RunPlugin({backup_url})'
            ))
        li.addContextMenuItems(context_items)


def show_wrestling_root(plugin_handle, addon):
    """
    Show wrestling root menu - organized transparently.
    
    Structure:
    - LIVE (24/7 channels + live events)
    - WWE (all WWE content organized)
    - OTHER PROMOTIONS (AEW, TNA, NWA, NJPW, ROH, Indy)
    - DOCUMENTARIES
    - INTERVIEWS  
    - SPECIAL MATCHES
    - MOVIES & TV
    - ARCHIVE
    """
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    categories = [
        {
            'title': 'LIVE',
            'description': 'Live 24/7 wrestling channels and live events',
            'action': 'wrestling_live',
        },
        {
            'title': 'WWE',
            'description': 'All WWE content (RAW, SmackDown, NXT, PPVs, WrestleMania)',
            'action': 'wrestling_wwe',
        },
        {
            'title': 'OTHER PROMOTIONS',
            'description': 'AEW, TNA, NWA, NJPW, ROH, Independent wrestling',
            'action': 'wrestling_other_promotions',
        },
        {
            'title': 'DOCUMENTARIES',
            'description': 'Wrestling documentaries and behind-the-scenes',
            'action': 'wrestling_documentaries',
        },
        {
            'title': 'INTERVIEWS',
            'description': 'Wrestling interviews and talk shows',
            'action': 'wrestling_interviews',
        },
        {
            'title': 'SPECIAL MATCHES',
            'description': 'Notable and historic wrestling matches',
            'action': 'wrestling_special_matches',
        },
        {
            'title': 'MOVIES & TV',
            'description': 'Wrestling-themed movies and TV shows',
            'action': 'wrestling_movies_tv',
        },
        {
            'title': 'ARCHIVE',
            'description': 'Historical wrestling content',
            'action': 'wrestling_archive',
        },
    ]
    
    for cat in categories:
        li = xbmcgui.ListItem(cat['title'])
        li.setInfo('video', {
            'title': cat['title'],
            'plot': cat['description'],
            'mediatype': 'video'
        })
        li.setArt({'thumb': icon, 'icon': icon, 'fanart': fanart})
        
        url = build_url(base_url, action=cat['action'])
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_wrestling_live(plugin_handle, addon):
    """Show all live wrestling content (24/7 channels + live events)."""
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    
    source = WrestlingContentSource()
    items = source.get_live_content()
    formatted = source.format_items(items, 'Wrestling > Live')
    
    for item in formatted:
        if not item.get('links'):
            continue
        
        li = xbmcgui.ListItem(item['title'])
        li.setInfo('video', {
            'title': item['title'],
            'plot': item.get('summary', ''),
            'mediatype': 'video'
        })
        li.setArt({
            'thumb': item.get('thumbnail') or icon,
            'icon': item.get('thumbnail') or icon,
            'fanart': item.get('fanart') or fanart
        })
        
        url = build_playable_url(item['primary_link'])
        add_backup_streams_context(li, item['links'])
        
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_wrestling_wwe(plugin_handle, addon):
    """
    Show WWE submenu.
    
    Categories:
    - RAW (457 episodes)
    - SmackDown (435 episodes)
    - NXT (episodes)
    - Other WWE Shows (documentaries, series)
    - WrestleMania
    - Pay-Per-View Events
    """
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    categories = [
        {'title': 'RAW', 'action': 'wrestling_wwe_raw', 'description': 'WWE Monday Night RAW episodes'},
        {'title': 'SmackDown', 'action': 'wrestling_wwe_smackdown', 'description': 'WWE Friday Night SmackDown episodes'},
        {'title': 'NXT', 'action': 'wrestling_wwe_nxt', 'description': 'WWE NXT episodes'},
        {'title': 'Other WWE Shows', 'action': 'wrestling_wwe_other_shows', 'description': 'WWE documentaries, series, and specials'},
        {'title': 'WrestleMania', 'action': 'wrestling_wwe_wrestlemania', 'description': 'WrestleMania events'},
        {'title': 'Pay-Per-View Events', 'action': 'wrestling_wwe_ppv', 'description': 'WWE PPV events (Royal Rumble, SummerSlam, etc.)'},
    ]
    
    for cat in categories:
        li = xbmcgui.ListItem(cat['title'])
        li.setInfo('video', {'title': cat['title'], 'plot': cat['description']})
        li.setArt({'thumb': icon, 'fanart': fanart})
        
        url = build_url(base_url, action=cat['action'])
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_wwe_episodes(plugin_handle, addon, show_method, show_title):
    """Generic function to show WWE show episodes."""
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    
    source = WrestlingContentSource()
    items = show_method()
    formatted = source.format_items(items, f'Wrestling > WWE > {show_title}')
    
    for item in formatted:
        if not item.get('links'):
            continue
        
        li = xbmcgui.ListItem(item['title'])
        li.setInfo('video', {
            'title': item['title'],
            'plot': item.get('summary', ''),
            'tvshowtitle': f'WWE {show_title}',
            'mediatype': 'episode'
        })
        li.setArt({
            'thumb': item.get('thumbnail') or icon,
            'icon': item.get('thumbnail') or icon,
            'fanart': item.get('fanart') or fanart
        })
        
        url = build_playable_url(item['primary_link'])
        add_backup_streams_context(li, item['links'])
        
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_wrestling_wwe_raw(plugin_handle, addon):
    """Show WWE RAW episodes (457 episodes)."""
    source = WrestlingContentSource()
    show_wwe_episodes(plugin_handle, addon, source.get_wwe_raw_episodes, 'RAW')


def show_wrestling_wwe_smackdown(plugin_handle, addon):
    """Show WWE SmackDown episodes (435 episodes)."""
    source = WrestlingContentSource()
    show_wwe_episodes(plugin_handle, addon, source.get_wwe_smackdown_episodes, 'SmackDown')


def show_wrestling_wwe_nxt(plugin_handle, addon):
    """Show WWE NXT episodes."""
    source = WrestlingContentSource()
    show_wwe_episodes(plugin_handle, addon, source.get_wwe_nxt_episodes, 'NXT')


def show_wrestling_wwe_other_shows(plugin_handle, addon):
    """Show other WWE shows (documentaries, series)."""
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    source = WrestlingContentSource()
    items = source.get_wwe_shows_menu()
    formatted = source.format_items(items, 'Wrestling > WWE > Other Shows')
    
    for item in formatted:
        li = xbmcgui.ListItem(item['title'])
        li.setInfo('video', {
            'title': item['title'],
            'plot': item.get('summary', '')
        })
        li.setArt({
            'thumb': item.get('thumbnail') or icon,
            'icon': item.get('thumbnail') or icon,
            'fanart': item.get('fanart') or fanart
        })
        
        # Check if folder or playable item
        if item['type'] == 'dir' and item.get('xml_url'):
            # This is a folder - need recursive parsing (implement as needed)
            # For now, skip or handle specially
            url = build_url(base_url, action='wrestling_fetch_xml', xml_url=quote_plus(item['xml_url']))
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
        elif item.get('links'):
            # Playable item
            url = build_playable_url(item['primary_link'])
            add_backup_streams_context(li, item['links'])
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_wrestling_wwe_wrestlemania(plugin_handle, addon):
    """Show WrestleMania events."""
    show_generic_category(plugin_handle, addon, 'wrestlemania', 'WrestleMania')


def show_wrestling_wwe_ppv(plugin_handle, addon):
    """Show WWE PPV events."""
    show_generic_category(plugin_handle, addon, 'ppv', 'PPV')


def show_wrestling_other_promotions(plugin_handle, addon):
    """Show other wrestling promotions menu."""
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    promotions = [
        {'title': 'AEW (All Elite Wrestling)', 'action': 'wrestling_aew', 'count': 17},
        {'title': 'TNA (Total Nonstop Action)', 'action': 'wrestling_tna', 'count': 6},
        {'title': 'NWA (National Wrestling Alliance)', 'action': 'wrestling_nwa', 'count': 5},
        {'title': 'NJPW (New Japan Pro Wrestling)', 'action': 'wrestling_njpw', 'count': 8},
        {'title': 'ROH (Ring of Honor)', 'action': 'wrestling_roh', 'count': 4},
        {'title': 'Independent Wrestling', 'action': 'wrestling_indy', 'count': 544},
    ]
    
    for promo in promotions:
        li = xbmcgui.ListItem(f"{promo['title']} ({promo['count']} items)")
        li.setArt({'thumb': icon, 'fanart': fanart})
        
        url = build_url(base_url, action=promo['action'])
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(plugin_handle)


def show_generic_category(plugin_handle, addon, category_key, category_name):
    """Generic function to display any wrestling category."""
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    source = WrestlingContentSource()
    
    # Map category_key to method
    method_map = {
        'wrestlemania': source.get_wwe_wrestlemania,
        'ppv': source.get_wwe_ppv,
        'aew': source.get_aew_content,
        'tna': source.get_tna_content,
        'nwa': source.get_nwa_content,
        'njpw': source.get_njpw_content,
        'roh': source.get_roh_content,
        'indy': source.get_indy_content,
        'documentaries': source.get_documentaries,
        'interviews': source.get_interviews,
        'special_matches': source.get_special_matches,
        'movies_tv': source.get_movies_tv,
        'archive': source.get_archive,
    }
    
    method = method_map.get(category_key)
    if not method:
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    items = method()
    formatted = source.format_items(items, f'Wrestling > {category_name}')
    
    for item in formatted:
        li = xbmcgui.ListItem(item['title'])
        li.setInfo('video', {
            'title': item['title'],
            'plot': item.get('summary', '')
        })
        li.setArt({
            'thumb': item.get('thumbnail') or icon,
            'icon': item.get('thumbnail') or icon,
            'fanart': item.get('fanart') or fanart
        })
        
        # Check if folder or playable
        if item['type'] == 'dir' and item.get('xml_url'):
            url = build_url(base_url, action='wrestling_fetch_xml', xml_url=quote_plus(item['xml_url']))
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
        elif item.get('links'):
            url = build_playable_url(item['primary_link'])
            add_backup_streams_context(li, item['links'])
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(plugin_handle)


# Individual promotion handlers
def show_wrestling_aew(plugin_handle, addon):
    """Show AEW content (17 items)."""
    show_generic_category(plugin_handle, addon, 'aew', 'AEW')


def show_wrestling_tna(plugin_handle, addon):
    """Show TNA content (6 items)."""
    show_generic_category(plugin_handle, addon, 'tna', 'TNA')


def show_wrestling_nwa(plugin_handle, addon):
    """Show NWA content (5 items)."""
    show_generic_category(plugin_handle, addon, 'nwa', 'NWA')


def show_wrestling_njpw(plugin_handle, addon):
    """Show NJPW content (8 items)."""
    show_generic_category(plugin_handle, addon, 'njpw', 'NJPW')


def show_wrestling_roh(plugin_handle, addon):
    """Show ROH content (4 items)."""
    show_generic_category(plugin_handle, addon, 'roh', 'ROH')


def show_wrestling_indy(plugin_handle, addon):
    """Show Independent wrestling content (544 items)."""
    show_generic_category(plugin_handle, addon, 'indy', 'Independent Wrestling')


# Other content categories
def show_wrestling_documentaries(plugin_handle, addon):
    """Show wrestling documentaries (4 items)."""
    show_generic_category(plugin_handle, addon, 'documentaries', 'Documentaries')


def show_wrestling_interviews(plugin_handle, addon):
    """Show wrestling interviews (25 items)."""
    show_generic_category(plugin_handle, addon, 'interviews', 'Interviews')


def show_wrestling_special_matches(plugin_handle, addon):
    """Show special wrestling matches (12 items)."""
    show_generic_category(plugin_handle, addon, 'special_matches', 'Special Matches')


def show_wrestling_movies_tv(plugin_handle, addon):
    """Show wrestling movies and TV shows (82 items)."""
    show_generic_category(plugin_handle, addon, 'movies_tv', 'Movies & TV')


def show_wrestling_archive(plugin_handle, addon):
    """Show wrestling archive (54 items)."""
    show_generic_category(plugin_handle, addon, 'archive', 'Archive')


def show_wrestling_fetch_xml(plugin_handle, addon, xml_url):
    """
    Dynamically fetch and display content from any XML URL.
    Used for recursive folder navigation.
    """
    icon = get_media_path(addon, 'icon.png')
    fanart = get_media_path(addon, 'fanart.jpg')
    base_url = sys.argv[0]
    
    source = WrestlingContentSource()
    xml_content = source.fetch_xml(xml_url)
    
    if not xml_content:
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    items = source.parse_xml(xml_content)
    formatted = source.format_items(items, 'Wrestling')
    
    for item in formatted:
        li = xbmcgui.ListItem(item['title'])
        li.setInfo('video', {
            'title': item['title'],
            'plot': item.get('summary', '')
        })
        li.setArt({
            'thumb': item.get('thumbnail') or icon,
            'icon': item.get('thumbnail') or icon,
            'fanart': item.get('fanart') or fanart
        })
        
        if item['type'] == 'dir' and item.get('xml_url'):
            url = build_url(base_url, action='wrestling_fetch_xml', xml_url=quote_plus(item['xml_url']))
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
        elif item.get('links'):
            url = build_playable_url(item['primary_link'])
            add_backup_streams_context(li, item['links'])
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(plugin_handle)
