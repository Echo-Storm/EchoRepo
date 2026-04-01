# -*- coding: utf-8 -*-
"""
League.do Source - Scrape events from super.league.do

Based on patterns from plugin.video.sporthdme:
- Extracts window.matches JSON from page
- Parses event structure with team info, channels, timestamps
"""

import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import xbmc

from .base import BaseSource


class LeagueDoSource(BaseSource):
    """super.league.do scraper source."""
    
    SOURCE_ID = "leaguedo"
    SOURCE_NAME = "League.do"
    
    # Site Configuration
    BASE_URL = "https://super.league.do"
    
    # Sport mappings: our normalized names -> league.do sport keywords
    SPORT_MAPPINGS = {
        'all': None,
        'nfl': 'american football',
        'nba': 'basketball',
        'nhl': 'ice hockey',
        'mlb': 'baseball',
        'golf': 'golf',
        'racing': ['motorsport', 'racing', 'formula', 'nascar'],
        'combat': ['mma', 'boxing', 'ufc', 'fight'],
        'wrestling': 'wrestling',
        'soccer': ['football', 'soccer'],
    }
    
    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': self.BASE_URL,
        })
        # Cache for events
        self._events_cache = {}
        
    def _fetch_page(self) -> Optional[str]:
        """
        Fetch the main page HTML.
        
        Returns:
            HTML content or None on error
        """
        try:
            response = self._session.get(self.BASE_URL, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            xbmc.log(f"[LeagueDo] Fetch error: {e}", xbmc.LOGERROR)
            return None
            
    def _extract_matches_json(self, html: str) -> Optional[List[Dict]]:
        """
        Extract matches JSON from page HTML.
        
        Based on sporthdme pattern:
        - Look for window.matches = JSON.parse(`[...]`)
        - Fallback to "matches" in script data
        
        Args:
            html: Page HTML content
            
        Returns:
            List of match dictionaries or None
        """
        # Primary pattern: window.matches = JSON.parse(`...`)
        pattern1 = r'window\.matches\s*=\s*JSON\.parse\(`(\[.+?\])`\)'
        match = re.search(pattern1, html, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                xbmc.log(f"[LeagueDo] JSON parse error (pattern1): {e}", xbmc.LOGWARNING)
                
        # Fallback pattern: embedded in Next.js data
        pattern2 = r'"matches"\s*:\s*(\[.+?\])\s*[,}]'
        match = re.search(pattern2, html.replace('\\', ''), re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                xbmc.log(f"[LeagueDo] JSON parse error (pattern2): {e}", xbmc.LOGWARNING)
                
        # Try finding any script with match-like data
        scripts = re.findall(r'<script[^>]*>(.+?)</script>', html, re.DOTALL)
        for script in scripts:
            if 'matchDate' in script or 'startTimestamp' in script:
                # Try to extract JSON array
                json_match = re.search(r'(\[.*?"team1".*?"team2".*?\])', script, re.DOTALL)
                if json_match:
                    try:
                        # Clean up escaped characters
                        json_str = json_match.group(1).replace('\\"', '"').replace('\\/', '/')
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
                        
        xbmc.log("[LeagueDo] Could not extract matches JSON", xbmc.LOGERROR)
        return None
        
    def _matches_sport(self, event: Dict, sport: str) -> bool:
        """
        Check if an event matches the requested sport.
        
        Args:
            event: Event dictionary
            sport: Requested sport type
            
        Returns:
            True if event matches
        """
        if sport == 'all':
            return True
            
        sport_keywords = self.SPORT_MAPPINGS.get(sport)
        if sport_keywords is None:
            return True
            
        # Get event sport/league info
        event_sport = event.get('sport', '').lower()
        event_league = event.get('league', '').lower()
        combined = f"{event_sport} {event_league}"
        
        if isinstance(sport_keywords, list):
            return any(kw in combined for kw in sport_keywords)
        else:
            return sport_keywords in combined
            
    def get_events(self, sport: str = 'all') -> List[Dict[str, Any]]:
        """
        Fetch events from super.league.do.
        
        Args:
            sport: Sport type filter
            
        Returns:
            List of standardized event dictionaries
        """
        html = self._fetch_page()
        if not html:
            return []
            
        matches = self._extract_matches_json(html)
        if not matches:
            return []
            
        events = []
        now_ms = time.time() * 1000
        
        for idx, match in enumerate(matches):
            try:
                # Skip if doesn't match sport filter
                if not self._matches_sport(match, sport):
                    continue
                    
                # Generate a unique ID
                event_id = f"ld_{idx}_{match.get('team1', '')[:3]}_{match.get('team2', '')[:3]}"
                
                # Extract team info
                team1 = match.get('team1', '')
                team2 = match.get('team2', '')
                name = f"{team1} vs {team2}" if team1 and team2 else team1 or "Unknown Event"
                
                # Parse timestamp
                start_timestamp = match.get('startTimestamp', 0)
                if isinstance(start_timestamp, str):
                    start_timestamp = int(start_timestamp)
                    
                # Handle milliseconds vs seconds
                if start_timestamp > 10000000000:  # Likely milliseconds
                    start_time = start_timestamp // 1000
                else:
                    start_time = start_timestamp
                    
                # Duration for live check
                duration = match.get('duration', 120)  # Default 2 hours
                duration_ms = duration * 60 * 1000
                
                # Check if live
                is_live = start_timestamp <= now_ms <= (start_timestamp + duration_ms)
                
                # Extract channels/links
                channels = []
                for ch in match.get('channels', []):
                    if isinstance(ch, str):
                        # Just a channel name string
                        channels.append({
                            'name': ch,
                            'links': [],
                            'language': 'EN',
                        })
                    elif isinstance(ch, dict):
                        channels.append({
                            'name': ch.get('name', 'Unknown'),
                            'links': ch.get('links', []),
                            'language': ch.get('language', 'EN'),
                        })
                        
                events.append({
                    'id': event_id,
                    'name': name,
                    'team1': team1,
                    'team2': team2,
                    'league': match.get('league', match.get('sport', '')),
                    'sport': match.get('sport', ''),
                    'start_time': start_time,
                    'time_display': self.format_time(start_time),
                    'is_live': is_live,
                    'icon': match.get('team1Img', ''),
                    'channels': channels,
                    '_raw': match,
                })
                
            except Exception as e:
                xbmc.log(f"[LeagueDo] Error parsing event: {e}", xbmc.LOGERROR)
                continue
                
        # Sort by start time
        events.sort(key=lambda x: x.get('start_time', 0))
        
        # Cache for stream lookup
        for event in events:
            self._events_cache[event['id']] = event
            
        xbmc.log(f"[LeagueDo] Found {len(events)} events for sport={sport}", xbmc.LOGINFO)
        return events
        
    def get_streams(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Get streams for an event.
        
        Args:
            event_id: Event ID from get_events
            
        Returns:
            List of stream dictionaries
        """
        event = self._events_cache.get(event_id)
        
        # Cache miss - re-fetch events to populate cache
        # This happens because each Kodi navigation creates a new source instance
        if not event:
            xbmc.log(f"[LeagueDo] Event {event_id} not in cache, re-fetching events", xbmc.LOGINFO)
            self.get_events('all')  # Repopulate cache
            event = self._events_cache.get(event_id)
            
        if not event:
            xbmc.log(f"[LeagueDo] Event {event_id} not found after re-fetch", xbmc.LOGWARNING)
            return []
            
        streams = []
        
        for channel in event.get('channels', []):
            channel_name = channel.get('name', 'Unknown')
            language = channel.get('language', 'EN')
            
            for link in channel.get('links', []):
                if isinstance(link, str):
                    stream_url = link
                else:
                    continue
                    
                # Determine resolver type
                if any(x in stream_url for x in ['.m3u8', '/live/', '/hls/']):
                    resolver = 'direct'
                elif any(x in stream_url for x in ['dabac', 'sansat', 'istorm', 'zvision', 
                                                    'glisco', 'bedsport', 'coolrea', 
                                                    'evfancy', 's2watch', 'vuen', 'gopst']):
                    resolver = 'embed'
                else:
                    resolver = 'direct'
                    
                streams.append({
                    'name': channel_name,
                    'url': stream_url,
                    'quality': 'HD',
                    'language': language,
                    'resolver': resolver,
                })
                
        xbmc.log(f"[LeagueDo] Found {len(streams)} streams for event {event_id}", xbmc.LOGINFO)
        return streams
