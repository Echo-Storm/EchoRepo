# -*- coding: utf-8 -*-
"""
Router - Handle URL routing and menu navigation.
"""

import json
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from urllib.parse import parse_qsl, quote_plus, urlencode


class Router:
    """Routes plugin requests to appropriate handlers."""
    
    def __init__(self, handle):
        self.handle = handle
        self.addon = xbmcaddon.Addon()
        self.addon_url = sys.argv[0]
        self.addon_name = self.addon.getAddonInfo('name')
        
    def route(self, paramstring):
        """Route the request based on parameters."""
        params = dict(parse_qsl(paramstring))
        action = params.get('action', 'main_menu')
        
        xbmc.log(f"[{self.addon_name}] Route: action={action}, params={params}", xbmc.LOGDEBUG)
        
        # Route to handler
        if action == 'main_menu':
            self._main_menu()
        elif action == 'sport':
            self._sport_menu(params.get('sport', ''))
        elif action == 'events':
            self._events_list(params.get('source', ''), params.get('sport', ''))
        elif action == 'streams':
            self._streams_list(params.get('event_id', ''), params.get('source', ''))
        elif action == 'play':
            # Handle both old format (single 'url') and new format (JSON 'urls')
            urls_json = params.get('urls', '')
            single_url = params.get('url', '')
            resolver = params.get('resolver', 'direct')
            
            if urls_json:
                # New format: JSON-encoded list of URLs
                try:
                    urls = json.loads(urls_json)
                except json.JSONDecodeError:
                    urls = [single_url] if single_url else []
            else:
                # Old format: single URL
                urls = [single_url] if single_url else []
                
            self._play_stream(urls, resolver)
        elif action == 'settings':
            self.addon.openSettings()
        elif action == 'resolveurl_settings':
            self._open_resolveurl_settings()
        elif action.startswith('wrestling') or action == 'play_wrestling':
            # Route all wrestling actions to the wrestling handler
            self._route_wrestling(action, params)
        elif action.startswith('fod') or action == 'play_fod':
            # Route all FOD (boxing/MMA) actions to the FOD handler
            self._route_fod(action, params)
        elif action.startswith('nfl') or action == 'play_nfl':
            # Route all NFL actions to the NFL handler
            self._route_nfl(action, params)
        elif action.startswith('racing') or action == 'play_racing':
            # Route all racing/motorsport actions to the racing handler
            self._route_racing(action, params)
        else:
            xbmc.log(f"[{self.addon_name}] Unknown action: {action}", xbmc.LOGWARNING)
            self._main_menu()
            
    def _main_menu(self):
        """Display the main menu."""
        # Get icons path
        icon_path = self.addon.getAddonInfo('path') + '/resources/icons/'
        fanart = self.addon.getAddonInfo('fanart')
        
        menu_items = [
            ('Live Sports (LeagueDo)', 'sport', {'sport': 'all'}, 'DefaultTVShows.png'),
            ('[COLOR cyan]MadPlay77 Live Sports[/COLOR]', 'events', {'source': 'madplay77', 'sport': 'all'}, 'DefaultTVShows.png'),
            ('NFL', 'sport', {'sport': 'nfl'}, 'DefaultTVShows.png'),
            ('NBA', 'sport', {'sport': 'nba'}, 'DefaultTVShows.png'),
            ('NHL', 'sport', {'sport': 'nhl'}, 'DefaultTVShows.png'),
            ('MLB', 'sport', {'sport': 'mlb'}, 'DefaultTVShows.png'),
            ('Golf', 'sport', {'sport': 'golf'}, 'DefaultTVShows.png'),
            ('[COLOR lime]Racing/Motorsport[/COLOR]', 'racing', {}, 'DefaultTVShows.png'),
            ('Boxing/MMA', 'sport', {'sport': 'combat'}, 'DefaultTVShows.png'),
            ('Wrestling', 'sport', {'sport': 'wrestling'}, 'DefaultTVShows.png'),
        ]
        
        for label, action, params, icon in menu_items:
            is_folder = action not in ('settings', 'resolveurl_settings')
            if action in ('settings', 'resolveurl_settings'):
                self._add_settings_item(label, action, params, icon, fanart)
            else:
                self._add_directory_item(label, action, params, icon, fanart, is_folder)
            
        xbmcplugin.setContent(self.handle, 'files')
        xbmcplugin.endOfDirectory(self.handle)
    
    def _open_resolveurl_settings(self):
        """Open ResolveURL settings dialog."""
        xbmc.log(f"[{self.addon_name}] Opening ResolveURL settings", xbmc.LOGINFO)
        try:
            import xbmcaddon
            try:
                xbmcaddon.Addon('script.module.resolveurl')
                xbmc.executebuiltin('Addon.OpenSettings(script.module.resolveurl)')
            except RuntimeError:
                xbmcgui.Dialog().ok(
                    'ResolveURL Not Found',
                    'ResolveURL addon is not installed.\n\n'
                    'Install it from your addon repository\n'
                    'to enable debrid playback.'
                )
        except Exception as e:
            xbmc.log(f"[{self.addon_name}] Error opening ResolveURL settings: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                self.addon_name,
                'Failed to open ResolveURL settings',
                xbmcgui.NOTIFICATION_ERROR
            )
        
    def _sport_menu(self, sport):
        """Display events for a specific sport or all sports."""
        # Wrestling has its own comprehensive handler
        if sport == 'wrestling':
            self._wrestling_menu()
            return
        
        # Combat sports (Boxing/MMA) use FOD handler
        if sport == 'combat':
            self._fod_menu()
            return
        
        # NFL gets its own menu with live + replays
        if sport == 'nfl':
            self._nfl_menu()
            return
            
        # Go directly to LeagueDo events (only working source)
        # In the future, add source selection when more sources work
        self._events_list('leaguedo', sport)
        
    def _events_list(self, source, sport):
        """Display events from a specific source."""
        fanart = self.addon.getAddonInfo('fanart')
        
        # Import source module dynamically
        try:
            if source == 'sportsfire':
                from lib.sources.sportsfire import SportsfireSource
                src = SportsfireSource()
            elif source == 'leaguedo':
                from lib.sources.leaguedo import LeagueDoSource
                src = LeagueDoSource()
            elif source == 'rblive77':
                from lib.sources.rblive77 import RBLive77Source
                src = RBLive77Source()
            elif source == 'madplay77':
                from lib.sources.madplay77 import MadPlay77Source
                src = MadPlay77Source()
            else:
                xbmcgui.Dialog().notification(self.addon_name, f"Unknown source: {source}", xbmcgui.NOTIFICATION_ERROR)
                return
                
            events = src.get_events(sport)
            
            if not events:
                # More helpful error message
                if source == 'leaguedo':
                    xbmcgui.Dialog().ok(
                        'LeagueDo - No Events',
                        'Could not load events from LeagueDo.\n\n'
                        'Possible causes:\n'
                        '• Site may be down or blocking requests\n'
                        '• Check Kodi log for details\n'
                        '• Try again in a few minutes'
                    )
                else:
                    xbmcgui.Dialog().notification(self.addon_name, "No events found", xbmcgui.NOTIFICATION_INFO)
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)
                return
                
            for event in events:
                # Format: [TIME] Team1 vs Team2 - League (LIVE indicator)
                time_str = event.get('time_display', '')
                name = event.get('name', 'Unknown Event')
                league = event.get('league', '')
                is_live = event.get('is_live', False)
                
                label = f"[COLOR cyan]{time_str}[/COLOR] "
                label += f"[COLOR {'lime' if is_live else 'white'}]{name}[/COLOR]"
                if league:
                    label += f" - [I]{league}[/I]"
                if is_live:
                    label += " [COLOR red][LIVE][/COLOR]"
                    
                params = {
                    'event_id': event.get('id', ''),
                    'source': source,
                }
                
                icon = event.get('icon', 'DefaultTVShows.png')
                self._add_directory_item(label, 'streams', params, icon, fanart, True)
                
            xbmcplugin.setContent(self.handle, 'videos')
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            xbmc.log(f"[{self.addon_name}] Error loading events: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(self.addon_name, f"Error: {e}", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            
    def _streams_list(self, event_id, source):
        """Display available streams for an event."""
        fanart = self.addon.getAddonInfo('fanart')
        
        try:
            if source == 'sportsfire':
                from lib.sources.sportsfire import SportsfireSource
                src = SportsfireSource()
            elif source == 'leaguedo':
                from lib.sources.leaguedo import LeagueDoSource
                src = LeagueDoSource()
            elif source == 'rblive77':
                from lib.sources.rblive77 import RBLive77Source
                src = RBLive77Source()
            elif source == 'madplay77':
                from lib.sources.madplay77 import MadPlay77Source
                src = MadPlay77Source()
            else:
                return
                
            streams = src.get_streams(event_id)
            
            if not streams:
                xbmcgui.Dialog().notification(self.addon_name, "No streams found", xbmcgui.NOTIFICATION_INFO)
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)
                return
                
            for stream in streams:
                label = stream.get('name', 'Stream')
                quality = stream.get('quality', '')
                lang = stream.get('language', '')
                
                if quality:
                    label += f" [{quality}]"
                if lang:
                    label += f" ({lang})"
                    
                # Handle both old format (single 'url') and new format (list 'urls')
                urls = stream.get('urls', [])
                if not urls:
                    # Fallback to old single-url format
                    single_url = stream.get('url', '')
                    urls = [single_url] if single_url else []
                
                if not urls:
                    continue
                    
                params = {
                    'urls': json.dumps(urls),  # JSON-encode the URL list
                    'resolver': stream.get('resolver', 'direct'),
                }
                
                self._add_directory_item(label, 'play', params, 'DefaultVideo.png', fanart, False)
                
            xbmcplugin.setContent(self.handle, 'videos')
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            xbmc.log(f"[{self.addon_name}] Error loading streams: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(self.addon_name, f"Error: {e}", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            
    def _play_stream(self, urls, resolver):
        """
        Play a stream URL with automatic fallback.
        
        Args:
            urls: List of URLs to try in sequence (or single URL string for backwards compat)
            resolver: Resolver type ('embed', 'debrid', or 'direct')
        """
        # Handle backwards compatibility with single URL string
        if isinstance(urls, str):
            urls = [urls] if urls else []
        
        if not urls:
            xbmcgui.Dialog().notification(self.addon_name, "No stream URLs available", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
            
        total_urls = len(urls)
        
        for attempt_num, url in enumerate(urls, 1):
            try:
                # Extract domain for logging/notification
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.split('.')[0]
                except Exception:
                    domain = 'unknown'
                
                # Show notification for fallback attempts (not first attempt)
                if attempt_num > 1:
                    xbmcgui.Dialog().notification(
                        self.addon_name,
                        f"Trying fallback source ({attempt_num}/{total_urls})",
                        xbmcgui.NOTIFICATION_INFO,
                        2000
                    )
                    
                import time
                attempt_start = time.time()
                xbmc.log(f"[{self.addon_name}] Attempt {attempt_num}/{total_urls} START: {domain}", xbmc.LOGINFO)
                
                resolved_url = None
                res = None
                
                # Try embed resolver first if specified or if it looks like an embed
                if resolver == 'embed':
                    from lib.resolvers.embed import EmbedResolver
                    res = EmbedResolver()
                    
                    # Check for dead domains first - skip this URL and try next
                    if res.is_dead_domain(url):
                        xbmc.log(f"[{self.addon_name}] Skipping dead domain: {domain}", xbmc.LOGWARNING)
                        if attempt_num == total_urls:
                            # Last attempt failed on dead domain
                            xbmcgui.Dialog().notification(
                                self.addon_name,
                                f"All sources offline",
                                xbmcgui.NOTIFICATION_WARNING,
                                3000
                            )
                        continue  # Try next URL
                        
                    resolved_url = res.resolve(url)
                    
                # Try ResolveURL for debrid + hosters
                elif resolver == 'debrid' or resolver == 'resolveurl':
                    from lib.resolvers.resolveurl_resolver import ResolveURLResolver
                    res = ResolveURLResolver()
                    if res.is_available():
                        resolved_url = res.resolve(url)
                    else:
                        xbmcgui.Dialog().notification(self.addon_name, "ResolveURL not installed", xbmcgui.NOTIFICATION_WARNING)
                        
                # Direct resolver - ONLY if resolver type is 'direct'
                elif resolver == 'direct':
                    from lib.resolvers.direct import DirectResolver
                    res = DirectResolver()
                    resolved_url = res.resolve(url)
                    
                if resolved_url:
                    # Success! Create playable item
                    elapsed = time.time() - attempt_start
                    xbmc.log(f"[{self.addon_name}] Attempt {attempt_num}/{total_urls} SUCCESS in {elapsed:.1f}s: {domain}", xbmc.LOGINFO)
                    
                    li = xbmcgui.ListItem(path=resolved_url)
                    li.setProperty('IsPlayable', 'true')
                    
                    # Set headers if needed
                    if res:
                        headers = res.get_headers()
                        if headers:
                            header_str = '|' + '&'.join([f"{k}={quote_plus(v)}" for k, v in headers.items()])
                            li.setPath(resolved_url + header_str)
                            
                    xbmcplugin.setResolvedUrl(self.handle, True, li)
                    return  # Success - exit function
                else:
                    # This URL failed, try next
                    elapsed = time.time() - attempt_start
                    xbmc.log(f"[{self.addon_name}] Attempt {attempt_num}/{total_urls} FAILED in {elapsed:.1f}s: {domain} (returned None)", xbmc.LOGWARNING)
                    continue
                    
            except Exception as e:
                elapsed = time.time() - attempt_start
                xbmc.log(f"[{self.addon_name}] Attempt {attempt_num}/{total_urls} ERROR in {elapsed:.1f}s: {e}", xbmc.LOGERROR)
                # Try next URL
                continue
                
        # All attempts failed
        xbmcgui.Dialog().notification(
            self.addon_name,
            f"All {total_urls} source(s) failed",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            
    def _add_directory_item(self, label, action, params, icon, fanart, is_folder):
        """Add a directory item to the listing."""
        url = self._build_url(action, params)
        
        li = xbmcgui.ListItem(label=label)
        li.setArt({
            'icon': icon,
            'thumb': icon,
            'fanart': fanart,
        })
        
        if not is_folder:
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': label})
            
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=url,
            listitem=li,
            isFolder=is_folder
        )
    
    def _add_settings_item(self, label, action, params, icon, fanart):
        """Add a settings/action item (not playable, not a folder)."""
        url = self._build_url(action, params)
        
        li = xbmcgui.ListItem(label=label)
        li.setArt({
            'icon': icon,
            'thumb': icon,
            'fanart': fanart,
        })
        # Don't set IsPlayable - this is just an action, not media
        li.setInfo('video', {'title': label})
            
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=url,
            listitem=li,
            isFolder=False
        )
        
    def _build_url(self, action, params=None):
        """Build a plugin URL."""
        if params is None:
            params = {}
        params['action'] = action
        return f"{self.addon_url}?{urlencode(params)}"
        
    def _wrestling_menu(self):
        """Display the wrestling root menu."""
        from lib import wrestling_handlers as wh
        wh.show_wrestling_root(self.handle, self.addon)
        
    def _route_wrestling(self, action, params):
        """Route wrestling-related actions to the wrestling handler."""
        from lib import wrestling as wr
        from urllib.parse import parse_qs
        
        # Convert params dict to parse_qs format (values as lists)
        params_qs = {k: [v] for k, v in params.items()}
        
        wr.route(action, params_qs, self.handle, self.addon, self.addon_url)
    
    def _fod_menu(self):
        """Display the FOD (boxing/MMA) root menu."""
        from lib import fod_handlers as fh
        fh.show_fod_root(self.handle, self.addon)
    
    def _nfl_menu(self):
        """Display NFL menu with live events and replays."""
        fanart = self.addon.getAddonInfo('fanart')
        
        # Live NFL events from LeagueDo
        self._add_directory_item(
            '[COLOR lime]Live NFL[/COLOR]',
            'events',
            {'source': 'leaguedo', 'sport': 'nfl'},
            'DefaultTVShows.png',
            fanart,
            True
        )
        
        # NFL Replays submenu
        self._add_directory_item(
            'NFL Replays',
            'nfl_main',
            {},
            'DefaultTVShows.png',
            fanart,
            True
        )
        
        xbmcplugin.setContent(self.handle, 'files')
        xbmcplugin.endOfDirectory(self.handle)
    
    def _route_fod(self, action, params):
        """Route FOD-related actions to the FOD handler."""
        from lib import fod
        from urllib.parse import parse_qs
        
        # Convert params dict to parse_qs format (values as lists)
        params_qs = {k: [v] for k, v in params.items()}
        
        fod.route(action, params_qs, self.handle, self.addon, self.addon_url)
    
    def _route_nfl(self, action, params):
        """Route NFL-related actions to the NFL handler."""
        from lib import nfl
        from urllib.parse import parse_qs
        
        # Convert params dict to parse_qs format (values as lists)
        params_qs = {k: [v] for k, v in params.items()}
        
        nfl.route(action, params_qs, self.handle, self.addon, self.addon_url)

    def _route_racing(self, action, params):
        """Route racing/motorsport actions to the racing handler."""
        from lib import racing
        
        racing.handle_racing_action(self.handle, self.addon, action, params)
