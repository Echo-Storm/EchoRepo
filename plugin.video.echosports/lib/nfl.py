# -*- coding: utf-8 -*-
"""
NFL Rewind Action Router for plugin.video.echosports

Routes NFL replay actions to appropriate handlers.
"""

from urllib.parse import unquote_plus
from lib import nfl_handlers as nh


def route(action, params, plugin_handle, addon, base_url):
    """
    Route NFL-related actions to handlers.
    
    Args:
        action: Action string (e.g., 'nfl_main', 'nfl_season_25')
        params: URL parameters as dict with list values
        plugin_handle: Kodi plugin handle
        addon: Addon instance
        base_url: Base plugin URL
    """
    if action == 'nfl' or action == 'nfl_main':
        nh.show_nfl_root(plugin_handle, addon)
    
    # Season menus
    elif action == 'nfl_season_25':
        nh.show_nfl_season_25(plugin_handle, addon)
    elif action == 'nfl_season_24':
        nh.show_nfl_season_24(plugin_handle, addon)
    elif action == 'nfl_season_23':
        nh.show_nfl_season_23(plugin_handle, addon)
    
    # Direct playoff access (optional shortcuts)
    elif action == 'nfl_superbowl':
        nh.show_nfl_superbowl(plugin_handle, addon)
    elif action == 'nfl_probowl':
        nh.show_nfl_probowl(plugin_handle, addon)
    elif action == 'nfl_conference':
        nh.show_nfl_conference(plugin_handle, addon)
    elif action == 'nfl_divisional':
        nh.show_nfl_divisional(plugin_handle, addon)
    elif action == 'nfl_wildcard':
        nh.show_nfl_wildcard(plugin_handle, addon)
    
    # Dynamic XML fetch (for nested navigation)
    elif action == 'nfl_fetch_xml':
        xml_url = unquote_plus(params.get('xml_url', [''])[0])
        nh.show_nfl_from_url(plugin_handle, addon, xml_url)
    
    # Playback - reuse FOD's play function since same format
    elif action == 'play_nfl':
        url = unquote_plus(params.get('url', [''])[0])
        play_nfl_stream(plugin_handle, url)
    
    else:
        # Default to main menu
        nh.show_nfl_root(plugin_handle, addon)


def play_nfl_stream(plugin_handle, url):
    """
    Resolve and play an NFL stream.
    
    All NFL content is magnets → debrid required.
    Same resolution chain as FOD.
    """
    import xbmc
    import xbmcgui
    import xbmcplugin
    
    if not url:
        xbmcgui.Dialog().notification('Echo Sports', 'No URL provided', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(plugin_handle, False, xbmcgui.ListItem())
        return
    
    xbmc.log(f"[NFL] Resolving: {url[:100]}", xbmc.LOGINFO)
    
    resolved_url = None
    resolver = None  # Keep reference for error tracking
    debrid_status = None
    
    # Detect link type - ORDER MATTERS! Check magnet/mega FIRST
    is_magnet = url.startswith('magnet:')
    is_mega = 'mega.nz' in url
    is_debrid_required = is_magnet or is_mega
    
    # Only check for direct stream if it's NOT a magnet/mega link
    is_direct = False
    if not is_debrid_required:
        is_direct = any(url.endswith(ext) for ext in ['.m3u8', '.mp4', '.mkv', '.avi'])
    
    xbmc.log(f"[NFL] Link type: magnet={is_magnet}, mega={is_mega}, direct={is_direct}", xbmc.LOGINFO)
    
    # 1. Direct links play as-is (unlikely for NFL, but just in case)
    if is_direct:
        resolved_url = url
        xbmc.log(f"[NFL] Direct stream", xbmc.LOGINFO)
    
    # 2. Try ResolveURL for magnets, mega, and hosters
    if not resolved_url:
        try:
            from lib.resolvers.resolveurl_resolver import ResolveURLResolver
            resolver = ResolveURLResolver()
            
            if resolver.is_available():
                # Log debrid status for debugging
                debrid_status = resolver.check_debrid_status()
                xbmc.log(f"[NFL] Debrid status: {debrid_status}", xbmc.LOGINFO)
                
                if is_debrid_required and not any([debrid_status['real_debrid'], 
                                                    debrid_status['premiumize'], 
                                                    debrid_status['all_debrid']]):
                    xbmc.log("[NFL] Debrid required but no debrid service configured!", xbmc.LOGWARNING)
                
                xbmc.log(f"[NFL] Trying ResolveURL...", xbmc.LOGINFO)
                resolved_url = resolver.resolve(url)
                
                if resolved_url:
                    xbmc.log(f"[NFL] ResolveURL success: {resolved_url[:60]}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[NFL] ResolveURL returned None", xbmc.LOGWARNING)
            else:
                xbmc.log("[NFL] ResolveURL not installed", xbmc.LOGWARNING)
        except Exception as e:
            xbmc.log(f"[NFL] ResolveURL error: {e}", xbmc.LOGERROR)
    
    # 3. For non-debrid hosters, try yt-dlp as fallback
    if not resolved_url and not is_debrid_required:
        try:
            from lib.resolvers.ytdlp import YTDLPResolver
            ytdlp = YTDLPResolver()
            
            xbmc.log(f"[NFL] Trying yt-dlp fallback...", xbmc.LOGINFO)
            resolved_url = ytdlp.resolve(url)
            
            if resolved_url:
                xbmc.log(f"[NFL] yt-dlp success", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[NFL] yt-dlp error: {e}", xbmc.LOGERROR)
    
    # Play or show error
    if resolved_url:
        li = xbmcgui.ListItem(path=resolved_url)
        li.setProperty('IsPlayable', 'true')
        
        xbmcplugin.setResolvedUrl(plugin_handle, True, li)
        xbmc.log(f"[NFL] Playing: {resolved_url[:80]}", xbmc.LOGINFO)
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
        
        xbmc.log(f"[NFL] Resolution failed. last_error={last_error}, debrid_configured={debrid_configured}", xbmc.LOGINFO)
        
        # Specific error messages
        if is_magnet or is_mega:
            if last_error == 'dead_link':
                xbmcgui.Dialog().ok('Link Dead / Removed', 
                    'This file has been removed or is no longer available.\n\n'
                    'The uploader may have deleted it from Mega.nz.\n'
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
        xbmc.log(f"[NFL] Failed: {url[:60]}", xbmc.LOGERROR)
