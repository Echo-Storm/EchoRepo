# -*- coding: utf-8 -*-
"""
RBLive77 Source - Live sports streams via protobuf API.

API Flow:
1. GET /sfver{hash}/api/match/live?sportType=0&stream=true → match list
2. GET /api/stream/detail?matchId=X&sportType=Y&streamId=Z&... → stream details
3. Extract field 120 (trex:// URL)
4. Convert trex:// to https:// and fetch → returns actual stream URL
5. Play stream with required headers

Reverse engineered from RBLive77_3_0_316_Fixed_Arm7CustomM0d.apk
See RBLIVE77_NOTES.md for full details.
"""

import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import xbmc

from .base import BaseSource
from .rblive77_protobuf import parse_rblive77_response


class RBLive77Source(BaseSource):
    """RBLive77 protobuf API source."""
    
    SOURCE_ID = "rblive77"
    SOURCE_NAME = "RBLive77"
    
    # API Configuration
    API_BASE = "https://apis-data-defra10.tcrbg61levl.cfd"
    EMBED_ORIGIN = "https://may.2f17ubowlsjn46easier.cfd"
    
    # Known sfver hashes (fallback list in case one fails)
    SFVER_HASHES = [
        "sfver497616003a329cca24df7051a36501175690b1",
        "sfver5642b2e9d79242bdbb07f1d58cb6c5a0",
    ]
    
    # Sport type mappings: normalized name -> RBLive77 sportType
    SPORT_MAPPINGS = {
        'all': 0,       # All sports
        'soccer': 1,    # Football/Soccer
        'nba': 2,       # Basketball
        'tennis': 3,    # Tennis
        'mlb': 4,       # Baseball
        'badminton': 12,
        'volleyball': 13,
        # Note: Boxing(5?), MMA(6?), NHL(7?), Golf(8?), Racing(9?) gaps exist
        # These may be disabled or use different IDs - need more traffic captures
    }
    
    # Reverse mapping for display
    SPORT_NAMES = {
        1: "Football",
        2: "Basketball",
        3: "Tennis",
        4: "Baseball",
        12: "Badminton",
        13: "Volleyball",
    }
    
    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({
            'origin': self.EMBED_ORIGIN,
            'referer': f'{self.EMBED_ORIGIN}/',
            'user-agent': 'rbapp/--dg-pd1-app-316/3.0.316/android_28_9/GooglePhone_GFE4J_armeabi-v7a/America_Indiana/Indianapolis/en',
            'Accept': 'application/x-protobuf,application/json',  # Accept both protobuf and JSON
        })
        # Cache for events and stream details
        self._events_cache = {}
        self._current_sfver = self.SFVER_HASHES[0]  # Start with first known hash
        
    def _build_match_url(self, sport_type: int = 0) -> str:
        """
        Build the match list URL with sfver prefix.
        
        Args:
            sport_type: RBLive77 sport type (0 = all)
            
        Returns:
            Full API URL
        """
        return f"{self.API_BASE}/{self._current_sfver}/api/match/live?language=0&sportType={sport_type}&stream=true"
        
    def _fetch_matches(self, sport_type: int = 0) -> Optional[Dict]:
        """
        Fetch match list from API.
        
        The API returns protobuf by default. We try JSON first, then protobuf.
        
        Args:
            sport_type: Sport type filter (0 = all)
            
        Returns:
            Parsed response dict or None on error
        """
        url = self._build_match_url(sport_type)
        
        try:
            response = self._session.get(url, timeout=15)
            response.raise_for_status()
            
            # Try JSON parse first
            try:
                data = response.json()
                xbmc.log(f"[RBLive77] Got JSON response from match list API", xbmc.LOGINFO)
                return data
            except json.JSONDecodeError:
                # Response is protobuf - parse it
                xbmc.log(f"[RBLive77] Response is protobuf, parsing with custom parser", xbmc.LOGINFO)
                parsed = parse_rblive77_response(response.content)
                
                if parsed:
                    xbmc.log(f"[RBLive77] Successfully parsed protobuf response", xbmc.LOGINFO)
                    return parsed
                else:
                    xbmc.log(f"[RBLive77] Failed to parse protobuf response", xbmc.LOGERROR)
                    return None
                
        except requests.RequestException as e:
            xbmc.log(f"[RBLive77] Match list fetch error: {e}", xbmc.LOGERROR)
            # Try next sfver hash if available
            current_index = self.SFVER_HASHES.index(self._current_sfver)
            if current_index < len(self.SFVER_HASHES) - 1:
                self._current_sfver = self.SFVER_HASHES[current_index + 1]
                xbmc.log(f"[RBLive77] Trying next sfver hash: {self._current_sfver}", xbmc.LOGINFO)
                return self._fetch_matches(sport_type)  # Retry with new hash
            return None
            
    def _parse_match(self, match_data: Dict) -> Optional[Dict]:
        """
        Parse a match entry from the API response.
        
        Based on captured protobuf structure (integer keys):
        {
          1: matchId,
          2: sportType,
          3: startTime (ms),
          4: status,
          10: { league info },
          30: [ match details, team1, team2 ],
          79: venue,
          90: hasStream
        }
        
        Args:
            match_data: Raw match dictionary from API
            
        Returns:
            Standardized event dict or None if parsing fails
        """
        try:
            xbmc.log(f"[RBLive77] Parsing match with keys: {list(match_data.keys())}", xbmc.LOGINFO)
            
            match_id = match_data.get(1, 0)
            sport_type = match_data.get(2, 0)
            start_time_ms = match_data.get(3, 0)
            has_stream = match_data.get(90, 0)
            
            xbmc.log(f"[RBLive77] Match basic fields: id={match_id}, sport={sport_type}, stream={has_stream}", xbmc.LOGINFO)
            
            # Log fields 100 and 150 to find streamId (safely handle null bytes)
            if 100 in match_data:
                field_100 = match_data[100]
                if isinstance(field_100, bytes):
                    xbmc.log(f"[RBLive77] Field 100: <bytes length={len(field_100)}> hex={field_100.hex()[:100]}", xbmc.LOGINFO)
                elif isinstance(field_100, list):
                    xbmc.log(f"[RBLive77] Field 100: <list length={len(field_100)}> first_10={field_100[:10]}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[RBLive77] Field 100: {repr(field_100)}", xbmc.LOGINFO)
            if 150 in match_data:
                xbmc.log(f"[RBLive77] Field 150: {match_data[150]} (type: {type(match_data[150]).__name__})", xbmc.LOGINFO)
            
            # Skip if no stream available
            if not has_stream:
                xbmc.log(f"[RBLive77] Skipping match {match_id} - no stream (field 90={has_stream})", xbmc.LOGINFO)
                return None
                
            # Parse league info (field 10)
            league_info = match_data.get(10, {})
            league_name = 'Unknown League'
            
            # Safely extract league name (field 10 -> 3 -> 2)
            if isinstance(league_info, dict):
                field_3 = league_info.get(3, {})
                if isinstance(field_3, dict):
                    league_name = field_3.get(2, league_name)
                elif isinstance(field_3, str):
                    league_name = field_3
            
            # Parse match details (field 30 is a dict with numbered keys, not a list)
            match_details = match_data.get(30, {})
            
            # Field 30 contains team/match info as numbered keys
            title = "Unknown Match"
            
            # Try to extract title from various possible locations
            # Sometimes it's in field 30.2, sometimes field 30.20, etc.
            if isinstance(match_details, dict):
                # Look for the first string value that looks like a match title
                for key in sorted(match_details.keys()):
                    item = match_details[key]
                    if isinstance(item, dict):
                        # Check field 2 within this item for title
                        item_title = item.get(2)
                        if isinstance(item_title, str) and len(item_title) > 3:
                            # Found a potential title, but let's use league name as fallback
                            pass
                            
            # Extract title from match details or use team names
            # The structure is complex - let's use league info for now
            title = league_name if league_name != 'Unknown League' else f"Match {match_id}"
                
            # Try to extract team names from title or field 30
            team1 = "Team 1"
            team2 = "Team 2"
            
            # Parse team info from field 30 if it's a dict with team data
            if isinstance(match_details, dict):
                # Field 30 might have numbered keys like {10: team1_info, 20: team2_info}
                # or {20: team1_info, 21: team2_info}
                for key in sorted(match_details.keys()):
                    item = match_details[key]
                    if isinstance(item, dict) and 3 in item:
                        # Field 3 often contains a name string
                        name_data = item.get(3)
                        if isinstance(name_data, str):
                            # Extract team name from the string (might have prefix bytes)
                            name = name_data.split('\x12')[-1] if '\x12' in name_data else name_data
                            name = name.strip('\x00\x08')
                            if name and team1 == "Team 1":
                                team1 = name
                            elif name and team2 == "Team 2":
                                team2 = name
                    
            # Build title from team names
            if team1 != "Team 1" and team2 != "Team 2":
                title = f"{team1} vs {team2}"
            elif team1 != "Team 1":
                title = team1
            else:
                title = league_name if league_name != 'Unknown League' else f"Match {match_id}"
                
            # Convert start time from milliseconds to seconds
            start_time = start_time_ms // 1000 if start_time_ms > 10000000000 else start_time_ms
            
            # Check if live (assume 3 hour duration for most sports)
            is_live = self.is_event_live(start_time, duration_minutes=180)
            
            # Generate event ID
            event_id = f"rb77_{match_id}_{sport_type}"
            
            # Extract ALL streamIds from fields 150-170 (multiple streams per match)
            # Different fields = different stream sources
            stream_ids = []
            for field_num in range(150, 171):
                if field_num in match_data:
                    field_value = match_data[field_num]
                    # Field might contain dict with stream info, or just the ID
                    if isinstance(field_value, dict):
                        # Extract from nested structure if needed
                        # Some fields have the streamId directly, others nested
                        # For now, skip dicts - we'll handle them if needed
                        xbmc.log(f"[RBLive77] Field {field_num} contains dict (URL data), skipping for now", xbmc.LOGINFO)
                    elif isinstance(field_value, int):
                        stream_ids.append(field_value)
                        xbmc.log(f"[RBLive77] Found streamId {field_value} in field {field_num}", xbmc.LOGINFO)
            
            # Use first streamId as primary (we'll add multi-stream support later)
            stream_id = stream_ids[0] if stream_ids else 0
            
            if not stream_id:
                xbmc.log(f"[RBLive77] WARNING: No streamId found in fields 150-170 for match {match_id}", xbmc.LOGWARNING)
            
            # Store raw data for stream fetching
            event = {
                'id': event_id,
                'name': title,
                'team1': team1,
                'team2': team2,
                'league': league_name,
                'sport': self.SPORT_NAMES.get(sport_type, f'Sport {sport_type}'),
                'start_time': start_time,
                'time_display': self.format_time(start_time),
                'is_live': is_live,
                'icon': '',  # Could extract team logos if needed
                'channels': [],  # Will be populated when streams are fetched
                '_raw': {
                    'match_id': match_id,
                    'sport_type': sport_type,
                    'stream_id': stream_id,  # Field 150 contains streamId
                }
            }
            
            xbmc.log(f"[RBLive77] Successfully parsed match: {event['name']}", xbmc.LOGINFO)
            return event
            
        except Exception as e:
            xbmc.log(f"[RBLive77] Error parsing match: {e}", xbmc.LOGERROR)
            import traceback
            xbmc.log(f"[RBLive77] Traceback: {traceback.format_exc()}", xbmc.LOGINFO)
            return None
            
    def get_events(self, sport: str = 'all') -> List[Dict[str, Any]]:
        """
        Fetch events from RBLive77 API.
        
        Args:
            sport: Sport type filter (normalized name)
            
        Returns:
            List of standardized event dictionaries
        """
        # Map sport to RBLive77 sport type
        sport_type = self.SPORT_MAPPINGS.get(sport, 0)
        
        xbmc.log(f"[RBLive77] Fetching events for sport={sport} (sportType={sport_type})", xbmc.LOGINFO)
        
        # Fetch match list
        response = self._fetch_matches(sport_type)
        if not response:
            xbmc.log(f"[RBLive77] No response from API", xbmc.LOGWARNING)
            return []
            
        # Debug: log parsed structure
        xbmc.log(f"[RBLive77] Parsed response keys: {list(response.keys())}", xbmc.LOGINFO)
        xbmc.log(f"[RBLive77] Field 3 value: {response.get(3)} (type: {type(response.get(3))})", xbmc.LOGINFO)
        
        # Check if response has expected structure
        # Expected: {3: "Success", 10: {1: [match_array]}}
        # Field 10.1 is an ARRAY of matches, not a dict with numbered keys
        status = response.get(3)
        if status not in ['Success', 0, '0']:
            xbmc.log(f"[RBLive77] API returned non-success: {status}", xbmc.LOGWARNING)
            return []
            
        data = response.get(10, {})
        
        # Field 10.1 should now be a list of matches (from protobuf special handling)
        matches_array = data.get(1, [])
        
        if isinstance(matches_array, list):
            xbmc.log(f"[RBLive77] Found {len(matches_array)} matches in array", xbmc.LOGINFO)
        else:
            xbmc.log(f"[RBLive77] Field 10.1 is {type(matches_array)}, not list - protobuf parse issue", xbmc.LOGWARNING)
            matches_array = []
        
        xbmc.log(f"[RBLive77] Total matches: {len(matches_array)}", xbmc.LOGINFO)
        
        if not matches_array:
            xbmc.log(f"[RBLive77] No matches in response", xbmc.LOGINFO)
            return []
            
        events = []
        for match in matches_array:
            # Debug: log first match structure
            if len(events) == 0:
                xbmc.log(f"[RBLive77] First match keys: {list(match.keys())}", xbmc.LOGINFO)
                xbmc.log(f"[RBLive77] First match field 10 type: {type(match.get(10))}", xbmc.LOGINFO)
                if 10 in match:
                    xbmc.log(f"[RBLive77] Field 10 contents: {match.get(10)}", xbmc.LOGINFO)
                    
            event = self._parse_match(match)
            if event:
                events.append(event)
                # Cache for stream lookup
                self._events_cache[event['id']] = event
                
        # Sort by start time
        events.sort(key=lambda x: x.get('start_time', 0))
        
        xbmc.log(f"[RBLive77] Found {len(events)} events", xbmc.LOGINFO)
        return events
        
    def _fetch_stream_detail(self, match_id: int, sport_type: int, stream_id: int = 0) -> Optional[Dict]:
        """
        Fetch stream detail for a specific match.
        
        Endpoint: /api/stream/detail?matchId=X&sportType=Y&streamId=Z&...
        
        Args:
            match_id: Match ID from match list
            sport_type: Sport type
            stream_id: Stream ID from match field 150
            
        Returns:
            Stream detail dict or None
        """
        # Build URL with streamId if available
        if stream_id:
            url = f"{self.API_BASE}/api/stream/detail?matchId={match_id}&sportType={sport_type}&streamId={stream_id}&siteType=2001&continent=NA&country=US&digit=pd1&withOriginal=true"
        else:
            # Fallback without streamId (may work for some streams)
            url = f"{self.API_BASE}/api/stream/detail?matchId={match_id}&sportType={sport_type}&siteType=2001&continent=NA&country=US&digit=pd1&withOriginal=true"
        
        try:
            response = self._session.get(url, timeout=15)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            
            if 'protobuf' in content_type.lower():
                xbmc.log(f"[RBLive77] Stream detail response is protobuf, parsing", xbmc.LOGINFO)
                try:
                    from .rblive77_protobuf import decode_protobuf
                    return decode_protobuf(response.content)
                except Exception as e:
                    xbmc.log(f"[RBLive77] Protobuf parsing error: {e}", xbmc.LOGERROR)
                    return None
            else:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    xbmc.log(f"[RBLive77] Stream detail response is not JSON", xbmc.LOGWARNING)
                    return None
                
        except requests.RequestException as e:
            xbmc.log(f"[RBLive77] Stream detail fetch error: {e}", xbmc.LOGERROR)
            return None
            
    def _resolve_trex_url(self, trex_url: str) -> Optional[str]:
        """
        Convert trex:// URL to actual stream URL.
        
        Pattern:
        1. trex://line.x1-cdn.me/{hash1}/{hash2}/{id}
        2. Convert to https://line.x1-cdn.me/{hash1}/{hash2}/{id}
        3. Fetch endpoint - returns actual stream URL as plain text
        4. Return stream URL
        
        Args:
            trex_url: trex:// protocol URL from API field 120
            
        Returns:
            Actual stream URL or None on error
        """
        if not trex_url.startswith('trex://'):
            xbmc.log(f"[RBLive77] Invalid trex:// URL: {trex_url}", xbmc.LOGWARNING)
            return None
            
        # Convert to HTTPS
        lookup_url = trex_url.replace('trex://', 'https://')
        
        xbmc.log(f"[RBLive77] Resolving trex:// URL: {lookup_url}", xbmc.LOGINFO)
        
        try:
            # Fetch the lookup endpoint
            response = requests.get(lookup_url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Response should be plain text with the actual stream URL
            actual_url = response.text.strip()
            
            if not actual_url:
                xbmc.log(f"[RBLive77] Empty response from trex:// lookup", xbmc.LOGWARNING)
                return None
                
            xbmc.log(f"[RBLive77] Resolved to: {actual_url[:80]}", xbmc.LOGINFO)
            return actual_url
            
        except requests.RequestException as e:
            xbmc.log(f"[RBLive77] trex:// resolution error: {e}", xbmc.LOGERROR)
            return None
            
    def get_streams(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Get streams for an event.
        
        This fetches stream details and resolves trex:// URLs.
        
        Args:
            event_id: Event ID from get_events
            
        Returns:
            List of stream dictionaries
        """
        event = self._events_cache.get(event_id)
        
        # Cache miss - re-fetch events
        if not event:
            xbmc.log(f"[RBLive77] Event {event_id} not in cache, re-fetching", xbmc.LOGINFO)
            self.get_events('all')
            event = self._events_cache.get(event_id)
            
        if not event:
            xbmc.log(f"[RBLive77] Event {event_id} not found", xbmc.LOGWARNING)
            return []
            
        # Extract match details
        match_id = event['_raw']['match_id']
        sport_type = event['_raw']['sport_type']
        stream_id = event['_raw'].get('stream_id', 0)
        
        xbmc.log(f"[RBLive77] Fetching streams for match_id={match_id}, sport_type={sport_type}, stream_id={stream_id}", xbmc.LOGINFO)
        
        # Fetch stream details
        stream_detail = self._fetch_stream_detail(match_id, sport_type, stream_id)
        
        if not stream_detail:
            xbmc.log(f"[RBLive77] No stream details for event {event_id}", xbmc.LOGWARNING)
            return []
            
        # Check for success (integer keys)
        if stream_detail.get(3) != 'Success':
            xbmc.log(f"[RBLive77] Stream detail returned non-success: {stream_detail.get(3)}", xbmc.LOGWARNING)
            return []
            
        # Extract stream data from field 10 -> 2 (integer keys)
        data = stream_detail.get(10, {})
        stream_data = data.get(2, {})
        
        if not stream_data:
            xbmc.log(f"[RBLive77] No stream data in response", xbmc.LOGWARNING)
            return []
            
        streams = []
        
        # Field 120 contains trex:// URL (integer key)
        trex_url = stream_data.get(120, '')
        
        if trex_url:
            # Resolve trex:// to actual stream URL
            actual_url = self._resolve_trex_url(trex_url)
            
            if actual_url:
                streams.append({
                    'name': 'Stream 1',
                    'url': actual_url,
                    'quality': 'HD',
                    'language': 'EN',
                    'resolver': 'direct',
                })
            else:
                xbmc.log(f"[RBLive77] Failed to resolve trex:// URL", xbmc.LOGWARNING)
        else:
            xbmc.log(f"[RBLive77] No trex:// URL in stream data (field 120)", xbmc.LOGWARNING)
            
        # Note: Field 4 contains encrypted stream token (not implemented)
        # If trex:// fails, we could add field 4 decryption as a fallback
        
        xbmc.log(f"[RBLive77] Found {len(streams)} streams for event {event_id}", xbmc.LOGINFO)
        return streams
