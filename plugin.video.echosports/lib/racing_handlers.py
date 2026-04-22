"""
Racing/Motorsport handlers for Echo Sports.

Uses PitSport source for live motorsport streams.
"""


def show_racing_menu(plugin_handle, addon):
    """Show racing/motorsport menu."""
    import xbmc
    import xbmcgui
    import xbmcplugin
    
    from lib.sources.pitsport import pitsport_source
    
    fanart = addon.getAddonInfo('fanart')
    
    categories = pitsport_source.get_categories()
    
    for cat in categories:
        li = xbmcgui.ListItem(label=cat['name'])
        li.setArt({
            'icon': 'DefaultFolder.png',
            'fanart': fanart,
        })
        
        url = f"plugin://{addon.getAddonInfo('id')}/?action=racing_category&category={cat['id']}"
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=True)
    
    xbmcplugin.setContent(plugin_handle, 'files')
    xbmcplugin.endOfDirectory(plugin_handle)


def show_racing_category(plugin_handle, addon, category_id):
    """Show events for a racing category."""
    import xbmc
    import xbmcgui
    import xbmcplugin
    from urllib.parse import quote
    
    from lib.sources.pitsport import pitsport_source
    
    fanart = addon.getAddonInfo('fanart')
    
    xbmc.log(f"[Echo Sports] Racing: Loading category {category_id}", xbmc.LOGINFO)
    
    # Show progress
    progress = xbmcgui.DialogProgress()
    progress.create('Echo Sports', 'Loading motorsport events...')
    
    try:
        events = pitsport_source.get_events(category_id)
        progress.close()
    except Exception as e:
        progress.close()
        xbmc.log(f"[Echo Sports] Racing error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Echo Sports', 'Failed to load events', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    if not events:
        # Show "no events" message
        li = xbmcgui.ListItem(label='[I]No events found[/I]')
        li.setArt({'icon': 'DefaultFile.png', 'fanart': fanart})
        xbmcplugin.addDirectoryItem(plugin_handle, '', li, isFolder=False)
        xbmcplugin.setContent(plugin_handle, 'files')
        xbmcplugin.endOfDirectory(plugin_handle)
        return
    
    xbmc.log(f"[Echo Sports] Racing: Found {len(events)} events", xbmc.LOGINFO)
    
    for event in events:
        label = pitsport_source.format_label(event)
        
        li = xbmcgui.ListItem(label=label)
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': event['title']})
        
        art = {'icon': 'DefaultVideo.png', 'fanart': fanart}
        if event.get('thumb'):
            art['thumb'] = event['thumb']
        li.setArt(art)
        
        url = f"plugin://{addon.getAddonInfo('id')}/?action=play_racing&url={quote(event['url'])}"
        xbmcplugin.addDirectoryItem(plugin_handle, url, li, isFolder=False)
    
    xbmcplugin.setContent(plugin_handle, 'videos')
    xbmcplugin.addSortMethod(plugin_handle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(plugin_handle)


def play_racing_stream(plugin_handle, url):
    """Resolve and play a racing stream."""
    import xbmc
    import xbmcgui
    import xbmcplugin
    
    from lib.sources.pitsport import pitsport_source
    
    if not url:
        xbmcgui.Dialog().notification('Echo Sports', 'No URL provided', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
    
    xbmc.log(f"[Echo Sports] Racing: Resolving {url[:80]}", xbmc.LOGINFO)
    
    # Show progress
    progress = xbmcgui.DialogProgress()
    progress.create('Echo Sports', 'Finding stream...')
    
    try:
        stream_url, referer = pitsport_source.resolve_stream(url)
        progress.close()
    except Exception as e:
        progress.close()
        xbmc.log(f"[Echo Sports] Racing resolve error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Stream Error', f'Failed to resolve stream:\n{str(e)[:100]}')
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
    
    if not stream_url:
        xbmcgui.Dialog().notification(
            'Echo Sports',
            'No active stream found - may not be live yet',
            xbmcgui.NOTIFICATION_INFO,
            4000
        )
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
    
    xbmc.log(f"[Echo Sports] Racing: Playing {stream_url[:80]}", xbmc.LOGINFO)
    
    # Create ListItem
    li = xbmcgui.ListItem(path=stream_url)
    li.setInfo('video', {'mediatype': 'video'})
    
    # Set MIME type for HLS streams
    if '.m3u8' in stream_url.lower():
        li.setMimeType('application/vnd.apple.mpegurl')
        li.setContentLookup(False)
        
        # Try to use inputstream.adaptive if available
        try:
            import xbmcaddon
            xbmcaddon.Addon('inputstream.adaptive')
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            if referer:
                li.setProperty('inputstream.adaptive.manifest_headers', 
                              f'Referer={referer}&User-Agent=Mozilla/5.0')
        except:
            # inputstream.adaptive not available, use built-in player
            pass
    
    # Add referer if we have one
    if referer and '|' not in stream_url:
        # Append headers to URL for non-ISA playback
        headers = f'Referer={referer}&User-Agent=Mozilla/5.0'
        if '.m3u8' not in stream_url.lower():
            stream_url_with_headers = f'{stream_url}|{headers}'
            li.setPath(stream_url_with_headers)
    
    xbmcplugin.setResolvedUrl(plugin_handle, True, li)
