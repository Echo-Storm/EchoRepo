"""Wrestling category router"""
from urllib.parse import unquote_plus
from lib import wrestling_handlers as wh


def route(action, params, plugin_handle, addon, base_url):
    if action == 'wrestling':
        wh.show_wrestling_root(plugin_handle, addon)
    elif action == 'play_wrestling':
        # Handle playback through yt-dlp resolver
        url = unquote_plus(params.get('url', [''])[0])
        headers_json = params.get('headers', [''])[0]
        play_wrestling_stream(plugin_handle, url, headers_json)
    elif action == 'wrestling_live':
        wh.show_wrestling_live(plugin_handle, addon)
    elif action == 'wrestling_wwe':
        wh.show_wrestling_wwe(plugin_handle, addon)
    elif action == 'wrestling_wwe_raw':
        wh.show_wrestling_wwe_raw(plugin_handle, addon)
    elif action == 'wrestling_wwe_smackdown':
        wh.show_wrestling_wwe_smackdown(plugin_handle, addon)
    elif action == 'wrestling_wwe_nxt':
        wh.show_wrestling_wwe_nxt(plugin_handle, addon)
    elif action == 'wrestling_wwe_other_shows':
        wh.show_wrestling_wwe_other_shows(plugin_handle, addon)
    elif action == 'wrestling_wwe_wrestlemania':
        wh.show_wrestling_wwe_wrestlemania(plugin_handle, addon)
    elif action == 'wrestling_wwe_ppv':
        wh.show_wrestling_wwe_ppv(plugin_handle, addon)
    elif action == 'wrestling_other_promotions':
        wh.show_wrestling_other_promotions(plugin_handle, addon)
    elif action == 'wrestling_aew':
        wh.show_wrestling_aew(plugin_handle, addon)
    elif action == 'wrestling_tna':
        wh.show_wrestling_tna(plugin_handle, addon)
    elif action == 'wrestling_nwa':
        wh.show_wrestling_nwa(plugin_handle, addon)
    elif action == 'wrestling_njpw':
        wh.show_wrestling_njpw(plugin_handle, addon)
    elif action == 'wrestling_roh':
        wh.show_wrestling_roh(plugin_handle, addon)
    elif action == 'wrestling_indy':
        wh.show_wrestling_indy(plugin_handle, addon)
    elif action == 'wrestling_documentaries':
        wh.show_wrestling_documentaries(plugin_handle, addon)
    elif action == 'wrestling_interviews':
        wh.show_wrestling_interviews(plugin_handle, addon)
    elif action == 'wrestling_special_matches':
        wh.show_wrestling_special_matches(plugin_handle, addon)
    elif action == 'wrestling_movies_tv':
        wh.show_wrestling_movies_tv(plugin_handle, addon)
    elif action == 'wrestling_archive':
        wh.show_wrestling_archive(plugin_handle, addon)
    elif action == 'wrestling_fetch_xml':
        xml_url = unquote_plus(params.get('xml_url', [''])[0])
        wh.show_wrestling_fetch_xml(plugin_handle, addon, xml_url)
    else:
        wh.show_wrestling_root(plugin_handle, addon)


def play_wrestling_stream(plugin_handle, url, headers_json=''):
    """
    Resolve and play a wrestling stream.
    
    Resolution order:
    1. Direct playback for m3u8/mp4/CDN streams
    2. yt-dlp (system) for supported sites
    3. ResolveURL for debrid + hosters
    """
    import xbmc
    import xbmcgui
    import xbmcplugin
    import json
    
    if not url:
        xbmcgui.Dialog().notification('Echo Sports', 'No URL provided', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
        
    xbmc.log(f"[Wrestling] Resolving: {url[:80]}", xbmc.LOGINFO)
    
    # Parse headers if provided
    headers = {}
    if headers_json:
        try:
            headers = json.loads(unquote_plus(headers_json))
        except:
            pass
    
    resolved_url = None
    playback_headers = headers.copy()
    
    # Check if it's already a direct stream
    is_direct = any(x in url.lower() for x in [
        '.m3u8', '.mp4', '.ts', '.m3u',
        'cloudfront.net', 'akamaihd.net', 'pluto.tv',
        'warnermediacdn.com'
    ])
    
    if is_direct:
        resolved_url = url
        xbmc.log(f"[Wrestling] Direct stream: {url[:80]}", xbmc.LOGINFO)
    else:
        # Try yt-dlp resolver (uses system yt-dlp, falls back to ResolveURL)
        try:
            from lib.resolvers.ytdlp import resolve_with_headers
            resolved_url, ytdlp_headers = resolve_with_headers(url)
            if ytdlp_headers:
                playback_headers.update(ytdlp_headers)
        except Exception as e:
            xbmc.log(f"[Wrestling] yt-dlp error: {e}", xbmc.LOGERROR)
            
        # Fallback: try ResolveURL directly for debrid + hosters
        if not resolved_url:
            try:
                from lib.resolvers.resolveurl_resolver import ResolveURLResolver
                resolver = ResolveURLResolver()
                if resolver.is_available() and resolver.can_resolve(url):
                    resolved_url = resolver.resolve(url)
                    xbmc.log(f"[Wrestling] ResolveURL resolved: {resolved_url[:80] if resolved_url else 'None'}", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[Wrestling] ResolveURL error: {e}", xbmc.LOGERROR)
    
    if resolved_url:
        # Build ListItem for playback
        li = xbmcgui.ListItem(path=resolved_url)
        
        # Add headers if needed
        if playback_headers:
            header_str = '&'.join([f'{k}={v}' for k, v in playback_headers.items()])
            li.setPath(f"{resolved_url}|{header_str}")
            
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(plugin_handle, True, li)
        xbmc.log(f"[Wrestling] Playing: {resolved_url[:80]}", xbmc.LOGINFO)
    else:
        xbmcgui.Dialog().notification('Echo Sports', 'Could not resolve stream', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        xbmc.log(f"[Wrestling] Failed to resolve: {url[:80]}", xbmc.LOGERROR)
