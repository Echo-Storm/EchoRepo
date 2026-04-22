# -*- coding: utf-8 -*-
"""
Fights on Demand (FOD) Action Router for plugin.video.echosports

Routes combat sports actions to appropriate handlers.
"""

from urllib.parse import unquote_plus
from lib import fod_handlers as fh


def route(action, params, plugin_handle, addon, base_url):
    """
    Route FOD-related actions to handlers.
    
    Args:
        action: Action string (e.g., 'fod_main', 'fod_ufc_ppv')
        params: URL parameters as dict with list values
        plugin_handle: Kodi plugin handle
        addon: Addon instance
        base_url: Base plugin URL
    """
    if action == 'fod' or action == 'fod_main':
        fh.show_fod_root(plugin_handle, addon)
    
    # Latest content
    elif action == 'fod_latest':
        fh.show_fod_latest(plugin_handle, addon)
    
    # UFC sections
    elif action == 'fod_ufc':
        fh.show_fod_ufc_menu(plugin_handle, addon)
    elif action == 'fod_ufc_ppv':
        fh.show_fod_ufc_ppv(plugin_handle, addon)
    elif action == 'fod_ufc_fight_night':
        fh.show_fod_ufc_fight_night(plugin_handle, addon)
    elif action == 'fod_ufc_espn':
        fh.show_fod_ufc_espn(plugin_handle, addon)
    elif action == 'fod_ufc_abc':
        fh.show_fod_ufc_abc(plugin_handle, addon)
    elif action == 'fod_ufc_bjj':
        fh.show_fod_ufc_bjj(plugin_handle, addon)
    elif action == 'fod_ufc_classic_ppv':
        fh.show_fod_ufc_classic_ppv(plugin_handle, addon)
    elif action == 'fod_ufc_classic_fn':
        fh.show_fod_ufc_classic_fn(plugin_handle, addon)
    elif action == 'fod_ufc_shows':
        fh.show_fod_ufc_shows(plugin_handle, addon)
    
    # MMA section
    elif action == 'fod_mma':
        fh.show_fod_mma(plugin_handle, addon)
    
    # Boxing sections
    elif action == 'fod_boxing':
        fh.show_fod_boxing(plugin_handle, addon)
    elif action == 'fod_boxing_free':
        fh.show_fod_boxing_free(plugin_handle, addon)
    
    # Non-debrid (free) sections
    elif action == 'fod_free':
        fh.show_fod_free_menu(plugin_handle, addon)
    elif action == 'fod_ufc_free':
        fh.show_fod_ufc_free(plugin_handle, addon)
    elif action == 'fod_mma_free':
        fh.show_fod_mma_free(plugin_handle, addon)
    
    # Dynamic XML fetch (for nested navigation)
    elif action == 'fod_fetch_xml':
        xml_url = unquote_plus(params.get('xml_url', [''])[0])
        fh.show_fod_from_url(plugin_handle, addon, xml_url)
    
    # Playback
    elif action == 'play_fod':
        url = unquote_plus(params.get('url', [''])[0])
        play_fod_stream(plugin_handle, url)
    
    else:
        # Default to main menu
        fh.show_fod_root(plugin_handle, addon)


def play_fod_stream(plugin_handle, url):
    """
    Resolve and play a FOD stream.
    
    Resolution chain:
    1. Magnets/Mega → ResolveURL (requires debrid)
    2. Direct links (.m3u8, .mp4, .mkv) → play directly (only if NOT magnet/mega)
    3. File hosters (luluvdo, dood, etc.) → ResolveURL or yt-dlp
    """
    import xbmc
    import xbmcgui
    import xbmcplugin
    
    if not url:
        xbmcgui.Dialog().notification('Echo Sports', 'No URL provided', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
    
    xbmc.log(f"[FOD] Resolving: {url[:100]}", xbmc.LOGINFO)
    
    resolved_url = None
    resolver = None  # Keep reference for error tracking
    debrid_status = None
    
    # Detect link type - ORDER MATTERS! Check magnet/mega FIRST
    is_magnet = url.startswith('magnet:')
    is_mega = 'mega.nz' in url
    is_debrid_required = is_magnet or is_mega
    
    # Only check for direct stream if it's NOT a magnet/mega link
    # (magnets often have .mp4/.mkv in their display name)
    is_direct = False
    if not is_debrid_required:
        is_direct = any(url.endswith(ext) for ext in ['.m3u8', '.mp4', '.mkv', '.avi'])
    
    xbmc.log(f"[FOD] Link type: magnet={is_magnet}, mega={is_mega}, direct={is_direct}", xbmc.LOGINFO)
    
    # 1. Direct links play as-is (only non-magnet/mega)
    if is_direct:
        resolved_url = url
        xbmc.log(f"[FOD] Direct stream", xbmc.LOGINFO)
    
    # 2. Try ResolveURL for magnets, mega, and hosters
    if not resolved_url:
        try:
            from lib.resolvers.resolveurl_resolver import ResolveURLResolver
            resolver = ResolveURLResolver()
            
            if resolver.is_available():
                # Log debrid status for debugging
                debrid_status = resolver.check_debrid_status()
                xbmc.log(f"[FOD] Debrid status: {debrid_status}", xbmc.LOGINFO)
                
                if is_debrid_required and not any([debrid_status['real_debrid'], 
                                                    debrid_status['premiumize'], 
                                                    debrid_status['all_debrid']]):
                    xbmc.log("[FOD] Debrid required but no debrid service configured!", xbmc.LOGWARNING)
                
                xbmc.log(f"[FOD] Trying ResolveURL...", xbmc.LOGINFO)
                resolved_url = resolver.resolve(url)
                
                if resolved_url:
                    xbmc.log(f"[FOD] ResolveURL success: {resolved_url[:60]}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[FOD] ResolveURL returned None", xbmc.LOGWARNING)
            else:
                xbmc.log("[FOD] ResolveURL not installed", xbmc.LOGWARNING)
        except Exception as e:
            xbmc.log(f"[FOD] ResolveURL error: {e}", xbmc.LOGERROR)
    
    # 3. For non-debrid hosters, try yt-dlp as fallback
    if not resolved_url and not is_debrid_required:
        try:
            from lib.resolvers.ytdlp import YTDLPResolver
            ytdlp = YTDLPResolver()
            
            xbmc.log(f"[FOD] Trying yt-dlp fallback...", xbmc.LOGINFO)
            resolved_url = ytdlp.resolve(url)
            
            if resolved_url:
                xbmc.log(f"[FOD] yt-dlp success", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[FOD] yt-dlp error: {e}", xbmc.LOGERROR)
    
    # Play or show error
    if resolved_url:
        li = xbmcgui.ListItem(path=resolved_url)
        li.setProperty('IsPlayable', 'true')
        
        # Add headers for some sources
        if 'luluvdo' in url or 'luluvid' in url:
            li.setProperty('inputstream.adaptive.manifest_headers', 
                          'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        xbmcplugin.setResolvedUrl(plugin_handle, True, li)
        xbmc.log(f"[FOD] Playing: {resolved_url[:80]}", xbmc.LOGINFO)
    else:
        # Use the SAME resolver instance to get error info
        last_error = 'unknown'
        debrid_configured = False
        
        if resolver:
            last_error = resolver.get_last_error()
            if debrid_status:
                debrid_configured = any([debrid_status['real_debrid'], 
                                        debrid_status['premiumize'], 
                                        debrid_status['all_debrid']])
        
        xbmc.log(f"[FOD] Resolution failed. last_error={last_error}, debrid_configured={debrid_configured}", xbmc.LOGINFO)
        
        # Specific error messages
        if is_magnet or is_mega:
            if last_error == 'dead_link':
                xbmcgui.Dialog().ok('Link Dead / Removed', 
                    'This file has been removed or is no longer available.\n\n'
                    'The uploader may have deleted it.\n'
                    'Try a different version or check for newer uploads.')
            elif not debrid_configured:
                xbmcgui.Dialog().ok('Debrid Not Configured', 
                    'No debrid service is authorized.\n\n'
                    'Go to Echo Sports Settings and click\n'
                    '"Open ResolveURL Settings" to authorize\n'
                    'Real-Debrid, Premiumize, or AllDebrid.')
            else:
                xbmcgui.Dialog().ok('Playback Failed', 
                    'ResolveURL failed to resolve this link.\n\n'
                    'Your debrid service may need re-authorization.\n'
                    'Check ResolveURL settings and try again.')
        else:
            xbmcgui.Dialog().notification('Echo Sports', 'Could not resolve stream', xbmcgui.NOTIFICATION_ERROR)
        
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        xbmc.log(f"[FOD] Failed: {url[:60]}", xbmc.LOGERROR)
