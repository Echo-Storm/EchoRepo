"""
Racing/Motorsport action router for Echo Sports.

Routes racing-related actions to appropriate handlers.
"""


def handle_racing_action(plugin_handle, addon, action, params):
    """
    Route racing actions to appropriate handlers.
    
    Args:
        plugin_handle: Kodi plugin handle
        addon: Addon instance
        action: Action string (racing, racing_category, play_racing)
        params: Dict of URL parameters
    """
    import xbmc
    
    from lib import racing_handlers as rh
    
    xbmc.log(f"[Echo Sports] Racing action: {action}, params: {params}", xbmc.LOGDEBUG)
    
    if action == 'racing':
        # Main racing menu
        rh.show_racing_menu(plugin_handle, addon)
        
    elif action == 'racing_category':
        # Show events for a category (live/schedule)
        category = params.get('category', 'live')
        rh.show_racing_category(plugin_handle, addon, category)
        
    elif action == 'play_racing':
        # Play a racing stream
        url = params.get('url', '')
        rh.play_racing_stream(plugin_handle, url)
        
    else:
        xbmc.log(f"[Echo Sports] Unknown racing action: {action}", xbmc.LOGWARNING)
        rh.show_racing_menu(plugin_handle, addon)
