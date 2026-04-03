# -*- coding: utf-8 -*-
"""
MadPlay77/FCTV77 Source - Live sports via APIs

Network: Same as RBLive77/RBTV+/FCTV33
Key Difference: Protobuf parser with proper field accumulation (works correctly!)

Based on:
- APK analysis: com_fctv77_app-release-318-v3_0_318.apk
- Traffic captures: HTTP Toolkit session April 3, 2026
- Discovery: Match list API returns 50+ events (vs RBLive77's broken 1-2)
"""

import struct
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import requests
import xbmc

from .base import BaseSource


class MadPlay77ProtobufParser:
    """
    Fixed protobuf parser with proper field accumulation.
    
    CRITICAL FIX: This parser correctly accumulates repeated fields into lists.
    RBLive77's parser overwrites repeated fields, so only the last value is kept.
    
    Result: MadPlay77 returns 50+ matches, RBLive77 returns 1-2 matches.
    """
    
    # Wire types
    VARINT = 0
    FIXED64 = 1
    LENGTH_DELIMITED = 2
    FIXED32 = 5
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        
    def read_varint(self) -> int:
        """Read a variable-length integer."""
        result = 0
        shift = 0
        while True:
            if self.pos >= len(self.data):
                raise ValueError("Unexpected end of data")
            byte = self.data[self.pos]
            self.pos += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return result
        
    def read_tag(self) -> Optional[Tuple[int, int]]:
        """Read a field tag. Returns (field_number, wire_type) or None if at end."""
        if self.pos >= len(self.data):
            return None
        tag = self.read_varint()
        field_number = tag >> 3
        wire_type = tag & 0x7
        return (field_number, wire_type)
        
    def read_length_delimited(self) -> bytes:
        """Read a length-prefixed byte array."""
        length = self.read_varint()
        if self.pos + length > len(self.data):
            raise ValueError("Length exceeds data bounds")
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result
        
    def read_fixed32(self) -> int:
        """Read a 32-bit fixed-length integer."""
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data for fixed32")
        result = struct.unpack('<I', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return result
        
    def read_fixed64(self) -> int:
        """Read a 64-bit fixed-length integer."""
        if self.pos + 8 > len(self.data):
            raise ValueError("Not enough data for fixed64")
        result = struct.unpack('<Q', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return result
        
    def parse_message(self) -> Dict[int, Any]:
        """
        Parse a protobuf message into a dict.
        
        CRITICAL: Accumulates repeated fields into lists (the fix!)
        """
        result = {}
        
        while True:
            tag_info = self.read_tag()
            if tag_info is None:
                break
                
            field_number, wire_type = tag_info
            
            # Read value based on wire type
            if wire_type == self.VARINT:
                value = self.read_varint()
                
            elif wire_type == self.LENGTH_DELIMITED:
                data = self.read_length_delimited()
                # Try to decode as string (UTF-8)
                try:
                    value = data.decode('utf-8')
                except UnicodeDecodeError:
                    # Try to parse as nested message
                    try:
                        parser = MadPlay77ProtobufParser(data)
                        value = parser.parse_message()
                    except:
                        # Store as bytes
                        value = data
                        
            elif wire_type == self.FIXED64:
                value = self.read_fixed64()
                
            elif wire_type == self.FIXED32:
                value = self.read_fixed32()
                
            else:
                # Unknown wire type, skip
                continue
            
            # CRITICAL FIX: Accumulate repeated fields into lists
            if field_number in result:
                # Field already exists - convert to list or append
                if not isinstance(result[field_number], list):
                    result[field_number] = [result[field_number]]
                result[field_number].append(value)
            else:
                result[field_number] = value
        
        return result


class MadPlay77Source(BaseSource):
    """
    MadPlay77/FCTV77 live sports source.
    
    Same network as RBLive77 but MUCH cleaner implementation:
    - Protobuf parser works correctly (arrays parse properly)
    - Match list API reliable (50+ matches returned)
    - sfver hash rotation (like RBLive77)
    """
    
    SOURCE_ID = "madplay77"
    SOURCE_NAME = "MadPlay77"
    
    # Configuration from APK analysis + traffic captures
    API_BASE = "https://apis-data-defra10.tcrbg61levl.cfd"
    EMBED_DOMAIN = "https://wv11.bvg0jdidiadnpopulation.cfd"
    LOGOS_CDN = "https://logos1.tcrbg61levl.cfd"
    
    # sfver hash rotation (from traffic captures - April 3, 2026)
    SFVER_HASHES = [
        "sfverda2a882084080604ed3d7830fa5907011248df",  # Primary (from match detail capture)
        "sfver4976163f66fb545957fb66980d9ab22b1575bb",  # Secondary (from match list)
        "sfver4976162013bc555846db693374599627b46919",  # Tertiary (fallback)
        # Add more as discovered - monitor API responses for hash rotation
    ]
    
    # Sport type mapping (observed from API responses)
    SPORT_TYPES = {
        'all': 0,
        'football': 1,      # Soccer
        'basketball': 2,
        'tennis': 3,
        'baseball': 4,
        'golf': 90,
        'badminton': 12,
        'volleyball': 13,
    }
    
    def __init__(self):
        super().__init__()
        self._match_cache = {}
        self._current_sfver_index = 0
        
    def _get_headers(self, for_embed=False):
        """
        Get request headers.
        
        Args:
            for_embed: True for embed pages, False for API calls
        """
        if for_embed:
            # Full WebView user-agent for embed pages
            return {
                'User-Agent': 'rbapp/--dg-foth-app-318/3.0.318/android_28_9/GooglePhone_GFE4J_arm64-v8a/America_Indiana/Indianapolis/en/Mozilla/5.0 (Linux; Android 9; GFE4J Build/PQ3A.190605.03171033; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.82 Safari/537.36',
                'Referer': f'{self.EMBED_DOMAIN}/',
                'X-Requested-With': 'com.fctv77.app',
                'Accept': '*/*',
            }
        else:
            # Short user-agent for API calls
            return {
                'origin': 'https://may.2f17ubowlsjn46easier.cfd',
                'referer': 'https://may.2f17ubowlsjn46easier.cfd/',
                'user-agent': 'rbapp/--dg-foth-app-318/3.0.318/android_28_9/GooglePhone_GFE4J_arm64-v8a/America_Indiana/Indianapolis/en',
                'Accept-Encoding': 'gzip',
                'Connection': 'Keep-Alive',
            }
    
    def _fetch_with_sfver_fallback(self, endpoint: str, params: Dict) -> Optional[bytes]:
        """
        Fetch from API with sfver hash fallback.
        
        Tries each hash in SFVER_HASHES until one works.
        """
        headers = self._get_headers(for_embed=False)
        
        for i, sfver in enumerate(self.SFVER_HASHES):
            url = f"{self.API_BASE}/{sfver}{endpoint}"
            
            try:
                xbmc.log(f"[MadPlay77] Fetching: {url} (sfver {i+1}/{len(self.SFVER_HASHES)})", xbmc.LOGINFO)
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    xbmc.log(f"[MadPlay77] Success with sfver index {i}: {len(response.content)} bytes", xbmc.LOGINFO)
                    self._current_sfver_index = i  # Remember working hash
                    return response.content
                    
                xbmc.log(f"[MadPlay77] sfver {i} failed: HTTP {response.status_code}", xbmc.LOGWARNING)
                
            except requests.RequestException as e:
                xbmc.log(f"[MadPlay77] sfver {i} error: {e}", xbmc.LOGWARNING)
                continue
        
        xbmc.log("[MadPlay77] All sfver hashes failed", xbmc.LOGERROR)
        return None
    
    def get_events(self, sport='all'):
        """
        Fetch live events.
        
        Args:
            sport: Sport type ('all', 'football', 'basketball', etc.)
        
        Returns:
            List of event dicts with keys: id, name, league, time_display, is_live, _raw
        """
        sport_type = self.SPORT_TYPES.get(sport, 0)
        
        xbmc.log(f"[MadPlay77] Fetching events for sport={sport} (sportType={sport_type})", xbmc.LOGINFO)
        
        # Fetch from API
        params = {
            'language': 0,
            'sportType': sport_type,
            'stream': 'true',
        }
        
        data = self._fetch_with_sfver_fallback('/api/match/live', params)
        if not data:
            xbmc.log("[MadPlay77] Failed to fetch match list", xbmc.LOGERROR)
            return []
        
        # Parse protobuf response
        try:
            parser = MadPlay77ProtobufParser(data)
            parsed = parser.parse_message()
            
            # Check status
            status = parsed.get(3, '')
            if status != 'Success':
                xbmc.log(f"[MadPlay77] API returned status: {status}", xbmc.LOGERROR)
                return []
            
            # Extract matches from field 10.1
            field_10 = parsed.get(10, {})
            if not isinstance(field_10, dict):
                xbmc.log(f"[MadPlay77] Field 10 is not dict: {type(field_10)}", xbmc.LOGERROR)
                return []
            
            matches = field_10.get(1, [])
            if not isinstance(matches, list):
                xbmc.log(f"[MadPlay77] Field 10.1 is not list: {type(matches)}", xbmc.LOGERROR)
                return []
            
            xbmc.log(f"[MadPlay77] Found {len(matches)} matches in response", xbmc.LOGINFO)
            
            # Convert to event format
            events = []
            for match in matches:
                if not isinstance(match, dict):
                    continue
                
                # Skip if no stream available
                if match.get(90) != 1:
                    continue
                
                match_id = match.get(1)
                start_time = match.get(3, 0)  # Milliseconds
                
                # Determine if live (within 6 hours of start time)
                now_ms = int(time.time() * 1000)
                time_diff_hours = abs(now_ms - start_time) / (1000 * 3600)
                is_live = time_diff_hours < 6
                
                # Format time display
                if start_time:
                    dt = datetime.fromtimestamp(start_time / 1000)
                    time_display = dt.strftime('%H:%M')
                else:
                    time_display = ''
                
                event = {
                    'id': str(match_id),
                    'name': self._extract_title(match),
                    'league': self._extract_league(match),
                    'time_display': time_display,
                    'is_live': is_live,
                    '_raw': match,
                }
                
                events.append(event)
                
                # Cache for stream lookup
                self._match_cache[str(match_id)] = match
            
            xbmc.log(f"[MadPlay77] Returning {len(events)} events with streams", xbmc.LOGINFO)
            return events
            
        except Exception as e:
            xbmc.log(f"[MadPlay77] Error parsing protobuf: {e}", xbmc.LOGERROR)
            return []
    
    def get_streams(self, event_id):
        """
        Get stream URLs for an event.
        
        Implementation strategy:
        1. Try direct API call (like RBLive77's /api/stream/detail)
        2. Fallback to embed page parsing
        3. Extract .m3u8 URLs or stream metadata
        
        Args:
            event_id: Match ID
        
        Returns:
            List of stream dicts with keys: name, url, resolver
        """
        xbmc.log(f"[MadPlay77] get_streams called for event_id={event_id}", xbmc.LOGINFO)
        
        match = self._match_cache.get(str(event_id))
        if not match:
            xbmc.log(f"[MadPlay77] Match {event_id} not in cache, re-fetching events", xbmc.LOGINFO)
            # Cache miss - repopulate like LeagueDo does
            self.get_events('all')
            match = self._match_cache.get(str(event_id))
            
        if not match:
            xbmc.log(f"[MadPlay77] Match {event_id} not found after re-fetch", xbmc.LOGWARNING)
            return []
        
        match_id = match.get(1)
        sport_type = match.get(2)
        xbmc.log(f"[MadPlay77] Resolving streams for matchId={match_id}, sportType={sport_type}", xbmc.LOGINFO)
        
        # Extract stream field (sport-specific)
        stream_field_num = self._get_stream_field_number(sport_type)
        stream_data = match.get(stream_field_num, {})
        
        if not stream_data or not isinstance(stream_data, dict):
            xbmc.log(f"[MadPlay77] No stream data in field {stream_field_num}", xbmc.LOGWARNING)
            return []
        
        # Stream data contains URL slugs
        match_slug = stream_data.get(20, '')
        competition_slug = stream_data.get(21, '')
        
        xbmc.log(f"[MadPlay77] Stream slugs: match={match_slug}, competition={competition_slug}", xbmc.LOGINFO)
        
        # Try multiple resolution strategies
        streams = []
        
        # Strategy 1: Try direct stream API (like RBLive77)
        streams = self._try_stream_api(match_id, sport_type)
        if streams:
            xbmc.log(f"[MadPlay77] Found {len(streams)} streams via direct API", xbmc.LOGINFO)
            return streams
        
        # Strategy 2: Try embed page parsing
        if match_slug:
            streams = self._try_embed_page(match_slug, sport_type, match_id)
            if streams:
                xbmc.log(f"[MadPlay77] Found {len(streams)} streams via embed page", xbmc.LOGINFO)
                return streams
        
        xbmc.log("[MadPlay77] All stream resolution strategies failed", xbmc.LOGWARNING)
        return []
    
    def _try_stream_api(self, match_id, sport_type):
        """
        Try direct API endpoints for stream data.
        
        DISCOVERED ENDPOINT (April 3, 2026 traffic capture):
        /sfver{HASH}/api/match/detail?matchId=X&language=0&sportType=Y&stream=true
        
        Returns protobuf with field 10.2.120 containing trex:// URL.
        Field 10.2.1 = streamId, field 10.2.9 = site type (e.g., 2001)
        """
        endpoints_to_try = [
            # PRIMARY: Confirmed working from traffic analysis
            f"/api/match/detail?matchId={match_id}&language=0&sportType={sport_type}&stream=true",
            # FALLBACK: Original guesses (kept for completeness)
            f"/api/stream/detail?matchId={match_id}&sportType={sport_type}&siteType=2001&continent=NA&country=US&digit=snd&withOriginal=true",
            f"/api/match/stream?matchId={match_id}&sportType={sport_type}",
        ]
        
        for endpoint in endpoints_to_try:
            for sfver_hash in self.SFVER_HASHES:
                url = f"{self.API_BASE}/{sfver_hash}{endpoint}"
                
                try:
                    response = requests.get(url, headers=self._get_api_headers(), timeout=8)
                    
                    if response.status_code == 200:
                        xbmc.log(f"[MadPlay77] API endpoint success: {endpoint}", xbmc.LOGINFO)
                        
                        # Try to parse as protobuf
                        try:
                            parser = MadPlay77ProtobufParser(response.content)
                            data = parser.parse_message()  # FIXED: was parse(), should be parse_message()
                            
                            # Look for stream URLs in response
                            streams = self._extract_streams_from_api_response(data)
                            if streams:
                                return streams
                        except Exception as e:
                            xbmc.log(f"[MadPlay77] Protobuf parse failed: {e}", xbmc.LOGWARNING)
                            
                            # Try JSON fallback
                            try:
                                json_data = response.json()
                                streams = self._extract_streams_from_json(json_data)
                                if streams:
                                    return streams
                            except:
                                pass
                                
                except requests.exceptions.RequestException as e:
                    xbmc.log(f"[MadPlay77] API request failed for {endpoint}: {e}", xbmc.LOGDEBUG)
                    continue
        
        return []
    
    def _try_embed_page(self, match_slug, sport_type, match_id):
        """
        Parse embed page to extract stream URLs.
        
        Fetches the Nuxt.js embed page and extracts window.__NUXT__ data.
        """
        # Build embed URL
        sport_name = self._type_to_sport(sport_type)
        embed_url = f"{self.EMBED_DOMAIN}/app-embbed/match/{sport_name}-{match_id}/overview.html"
        
        xbmc.log(f"[MadPlay77] Fetching embed page: {embed_url}", xbmc.LOGINFO)
        
        try:
            response = requests.get(embed_url, headers=self._get_embed_headers(), timeout=15)
            
            if response.status_code == 200:
                # Look for .m3u8 URLs in HTML
                import re
                m3u8_urls = re.findall(r'https?://[^\s<>"\']+\.m3u8[^\s<>"\']*', response.text)
                
                if m3u8_urls:
                    xbmc.log(f"[MadPlay77] Found {len(m3u8_urls)} .m3u8 URLs in embed page", xbmc.LOGINFO)
                    
                    streams = []
                    for i, url in enumerate(m3u8_urls, 1):
                        streams.append({
                            'name': f'Stream {i}',
                            'url': url,
                            'resolver': 'direct'
                        })
                    return streams
                
                # Try to extract from window.__NUXT__ (more complex)
                nuxt_match = re.search(r'window\.__NUXT__=(.+?);</script>', response.text, re.DOTALL)
                if nuxt_match:
                    xbmc.log("[MadPlay77] Found window.__NUXT__ data, attempting parse", xbmc.LOGINFO)
                    # This is complex JavaScript - would need js2py or similar
                    # For now, log that we found it but can't parse
                    xbmc.log("[MadPlay77] window.__NUXT__ parsing not implemented - needs js2py", xbmc.LOGDEBUG)
                
            elif response.status_code == 403:
                xbmc.log("[MadPlay77] Embed page returned 403 - Cloudflare block", xbmc.LOGWARNING)
            else:
                xbmc.log(f"[MadPlay77] Embed page returned {response.status_code}", xbmc.LOGWARNING)
                
        except requests.exceptions.RequestException as e:
            xbmc.log(f"[MadPlay77] Embed page fetch failed: {e}", xbmc.LOGWARNING)
        
        return []
    
    def _extract_streams_from_api_response(self, data: dict) -> List[Dict[str, Any]]:
        """
        Extract stream URLs from protobuf API response.
        
        Expected structure (from /api/match/detail):
        {
          "3": "Success",
          "10": {
            "1": { /* match data */ },
            "2": {
              "1": streamId,      // e.g., 676700
              "9": siteType,      // e.g., 2001
              "50": matchId,      // original matchId
              "120": "trex://..."  // Stream URL to resolve
            }
          }
        }
        """
        streams = []
        
        # Check status
        if data.get(3) != 'Success':
            xbmc.log("[MadPlay77] API response status != Success", xbmc.LOGWARNING)
            return streams
        
        # Look for stream data in field 10.2
        field_10 = data.get(10, {})
        if isinstance(field_10, dict):
            stream_data = field_10.get(2, {})
            
            if isinstance(stream_data, dict):
                # Log stream metadata for debugging
                stream_id = stream_data.get(1)
                site_type = stream_data.get(9)
                match_id = stream_data.get(50)
                xbmc.log(f"[MadPlay77] Stream data: streamId={stream_id}, siteType={site_type}, matchId={match_id}", xbmc.LOGINFO)
                
                # Check for trex:// URLs (PRIMARY method)
                trex_url = stream_data.get(120)
                if trex_url and isinstance(trex_url, str) and trex_url.startswith('trex://'):
                    xbmc.log(f"[MadPlay77] Found trex:// URL: {trex_url}", xbmc.LOGINFO)
                    # Convert trex:// to https:// and fetch
                    actual_url = self._resolve_trex_url(trex_url)
                    if actual_url:
                        streams.append({
                            'name': 'Main Stream',
                            'url': actual_url,
                            'resolver': 'direct'
                        })
                        xbmc.log(f"[MadPlay77] Resolved to M3U8: {actual_url[:100]}...", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[MadPlay77] No trex:// URL in field 120 (value: {stream_data.get(120)})", xbmc.LOGINFO)
                
                # FALLBACK: Check for direct URLs in other fields
                for field_num in range(100, 200):
                    value = stream_data.get(field_num)
                    if isinstance(value, str) and ('.m3u8' in value or 'http' in value):
                        streams.append({
                            'name': f'Stream {len(streams) + 1}',
                            'url': value,
                            'resolver': 'direct'
                        })
                        xbmc.log(f"[MadPlay77] Found direct URL in field {field_num}", xbmc.LOGINFO)
            else:
                xbmc.log("[MadPlay77] Field 10.2 is not a dict", xbmc.LOGINFO)
        else:
            xbmc.log("[MadPlay77] Field 10 is not a dict", xbmc.LOGINFO)
        
        return streams
    
    def _extract_streams_from_json(self, data: dict) -> List[Dict[str, Any]]:
        """Extract stream URLs from JSON response."""
        streams = []
        
        # Look for common JSON patterns
        # This is a fallback - actual structure depends on API response
        if 'streams' in data:
            for stream in data.get('streams', []):
                if 'url' in stream:
                    streams.append({
                        'name': stream.get('name', 'Stream'),
                        'url': stream['url'],
                        'resolver': 'direct'
                    })
        
        return streams
    
    def _resolve_trex_url(self, trex_url: str) -> Optional[str]:
        """
        Resolve trex:// protocol to actual stream URL.
        
        Pattern: trex://domain:port/path → http(s)://domain:port/path (direct stream)
        
        NOTE: trex:// URLs return BINARY STREAM DATA, not M3U8 playlists!
        We convert the protocol and return the HTTP(S) URL directly.
        """
        try:
            # Parse the trex URL to determine protocol
            # trex://line.trxdnscloud.ru:80/... → http://... (port 80 = HTTP)
            # trex://line.trxdnscloud.ru:443/... → https://... (port 443 = HTTPS)
            if ':80/' in trex_url or trex_url.endswith(':80'):
                # Port 80 = use HTTP
                stream_url = trex_url.replace('trex://', 'http://')
            else:
                # Other ports (or no port) = use HTTPS
                stream_url = trex_url.replace('trex://', 'https://')
            
            xbmc.log(f"[MadPlay77] Converted trex:// to direct stream: {stream_url}", xbmc.LOGINFO)
            return stream_url
            
        except Exception as e:
            xbmc.log(f"[MadPlay77] trex:// conversion failed: {e}", xbmc.LOGWARNING)
            return None
    
    def _get_stream_field_number(self, sport_type):
        """
        Get the field number containing stream data for a sport.
        
        Pattern: Field 150 + sport_type offset (mostly)
        Exception: Golf (90) uses field 200
        """
        if sport_type == 90:  # Golf
            return 200
        elif sport_type and sport_type <= 13:
            return 150 + sport_type
        else:
            return 150  # Default
    
    def _extract_title(self, match):
        """Extract match title from field 30."""
        field_30 = match.get(30)
        
        if not field_30:
            return f"Match {match.get(1, 'Unknown')}"
        
        # If it's a string, clean and return it
        if isinstance(field_30, str):
            title = field_30.replace('\x12', '').replace('\x08\x00', '')
            return title.strip()
        
        # If it's a list, first item is usually the title
        if isinstance(field_30, list) and len(field_30) > 0:
            first_item = field_30[0]
            if isinstance(first_item, str):
                title = first_item.replace('\x12', '').replace('\x08\x00', '')
                return title.strip()
        
        # Fallback
        return f"Match {match.get(1, 'Unknown')}"
    
    def _extract_league(self, match):
        """Extract league name from field 10."""
        field_10 = match.get(10)
        
        if not field_10 or not isinstance(field_10, dict):
            return ''
        
        # Field 10.3 often contains league name
        field_10_3 = field_10.get(3)
        if isinstance(field_10_3, str):
            league = field_10_3.replace('\x08\x00\x12', '').replace('\x08\x00', '')
            return league.strip()
        
        return ''
    
    def _get_api_headers(self):
        """Get headers for API calls (match list, stream detail)."""
        return {
            'origin': 'https://may.2f17ubowlsjn46easier.cfd',
            'referer': 'https://may.2f17ubowlsjn46easier.cfd/',
            'user-agent': 'rbapp/--dg-foth-app-318/3.0.318/android_28_9/GooglePhone_GFE4J_arm64-v8a/America_Indiana/Indianapolis/en',
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
        }
    
    def _get_embed_headers(self):
        """Get headers for embed page requests (with full WebView user-agent)."""
        return {
            'User-Agent': 'rbapp/--dg-foth-app-318/3.0.318/android_28_9/GooglePhone_GFE4J_arm64-v8a/America_Indiana/Indianapolis/en/Mozilla/5.0 (Linux; Android 9; GFE4J Build/PQ3A.190605.03171033; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.82 Safari/537.36',
            'Referer': f'{self.EMBED_DOMAIN}/',
            'X-Requested-With': 'com.fctv77.app',
            'Accept': '*/*',
        }
    
    def _type_to_sport(self, sport_type):
        """Convert sport type number to name."""
        reverse_map = {v: k for k, v in self.SPORT_TYPES.items() if k != 'all'}
        return reverse_map.get(sport_type, 'unknown')
