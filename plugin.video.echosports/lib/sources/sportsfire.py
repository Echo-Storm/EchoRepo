# -*- coding: utf-8 -*-
"""
Sportsfire Source - Fetch events from Sportsfire API.

API Details (extracted from Sportsfire APK):
- Base URL: https://spfire.work/tv/index.php?case=
- Auth Token: MD5("23232323") = 9120163167c05aed85f30bf88495bd89
- Method: HTTP POST with form-encoded body
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional

import requests
import xbmc

from .base import BaseSource


class SportsfireSource(BaseSource):
    """Sportsfire API source."""
    
    SOURCE_ID = "sportsfire"
    SOURCE_NAME = "Sportsfire"
    
    # API Configuration
    API_BASE = "https://spfire.work/tv/index.php?case="
    # Token is MD5 of "23232323"
    AUTH_TOKEN = "9120163167c05aed85f30bf88495bd89"
    
    # Sport mappings: our normalized names -> Sportsfire match_type_id
    # These IDs come from get_all_match_types response
    SPORT_MAPPINGS = {
        'all': None,  # No filter
        'nfl': '1',   # American Football
        'nba': '7',   # Basketball
        'nhl': '11',  # Hockey
        'mlb': '6',   # Baseball
        'golf': '25', # Golf (guess, needs verification)
        'racing': '23', # Motor Sports (guess)
        'combat': '3',  # MMA/Boxing
        'wrestling': '3', # Use combat for now
        'soccer': '2',  # Football (soccer)
    }
    
    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'app-token': self.AUTH_TOKEN,
            'User-Agent': 'USER-AGENT-tvtap-APP-V2',
        })
        # Cache for events (by sport)
        self._events_cache = {}
        
    def _api_request(self, endpoint: str, data: Dict[str, str] = None) -> Optional[Dict]:
        """
        Make an API request to Sportsfire.
        
        Args:
            endpoint: API endpoint (e.g., 'get_schedule_by_type')
            data: POST data dictionary
            
        Returns:
            JSON response or None on error
        """
        url = f"{self.API_BASE}{endpoint}"
        
        try:
            if data:
                response = self._session.post(url, data=data, timeout=15)
            else:
                response = self._session.post(url, timeout=15)
                
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            xbmc.log(f"[Sportsfire] API error: {e}", xbmc.LOGERROR)
            return None
        except json.JSONDecodeError as e:
            xbmc.log(f"[Sportsfire] JSON decode error: {e}", xbmc.LOGERROR)
            return None
            
    def get_match_types(self) -> List[Dict[str, str]]:
        """
        Fetch available sport categories.
        
        Returns:
            List of {'id': '1', 'name': 'American Football'}
        """
        response = self._api_request('get_all_match_types')
        
        if not response or not response.get('success'):
            return []
            
        match_types = response.get('msg', {}).get('match_types', [])
        return [{'id': mt.get('pk_id', ''), 'name': mt.get('name', '')} for mt in match_types]
        
    def get_events(self, sport: str = 'all') -> List[Dict[str, Any]]:
        """
        Fetch events for a sport category.
        
        Args:
            sport: Sport type ('all', 'nfl', 'nba', etc.)
            
        Returns:
            List of standardized event dictionaries
        """
        # Map sport to Sportsfire match_type_id
        match_type_id = self.SPORT_MAPPINGS.get(sport)
        
        # Build POST data
        data = {}
        if match_type_id:
            data['type'] = match_type_id
            
        response = self._api_request('get_schedule_by_type', data)
        
        if not response or not response.get('success'):
            xbmc.log(f"[Sportsfire] No events returned for sport={sport}", xbmc.LOGWARNING)
            return []
            
        schedulers = response.get('msg', {}).get('schedulers', [])
        events = []
        
        for sched in schedulers:
            try:
                event_id = sched.get('pk_id', '')
                team1 = sched.get('team1', '')
                team2 = sched.get('team2', '')
                name = sched.get('name', f"{team1} vs {team2}")
                
                # Parse timestamps
                start_time = int(sched.get('start_time', 0))
                duration = int(sched.get('duration', 180))  # Default 3 hours
                
                # Check if live
                is_live = sched.get('is_live', '0') == '1'
                if not is_live:
                    is_live = self.is_event_live(start_time, duration)
                    
                # Build channel list
                channels = []
                for ch in sched.get('channels', []):
                    channels.append({
                        'id': ch.get('pk_id', ''),
                        'name': ch.get('channel_name', ''),
                        'stream_encrypted': ch.get('http_stream', ''),  # Encrypted, need to decrypt
                        'country': ch.get('country', ''),
                    })
                    
                events.append({
                    'id': event_id,
                    'name': name,
                    'team1': team1,
                    'team2': team2,
                    'league': sched.get('category_name', sched.get('series_type', '')),
                    'sport': sched.get('match_type_id', ''),
                    'start_time': start_time,
                    'time_display': self.format_time(start_time),
                    'is_live': is_live,
                    'icon': '',  # Could add team logos
                    'channels': channels,
                    '_raw': sched,  # Keep raw data for debugging
                })
                
            except Exception as e:
                xbmc.log(f"[Sportsfire] Error parsing event: {e}", xbmc.LOGERROR)
                continue
                
        # Sort by start time
        events.sort(key=lambda x: x.get('start_time', 0))
        
        # Cache for stream lookup
        for event in events:
            self._events_cache[event['id']] = event
            
        xbmc.log(f"[Sportsfire] Found {len(events)} events for sport={sport}", xbmc.LOGINFO)
        return events
        
    def get_streams(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Fetch available streams for an event.
        
        Args:
            event_id: Event ID from get_events
            
        Returns:
            List of stream dictionaries
        """
        # Look up event from cache
        event = self._events_cache.get(event_id)
        
        # Cache miss - re-fetch events to populate cache
        # This happens because each Kodi navigation creates a new source instance
        if not event:
            xbmc.log(f"[Sportsfire] Event {event_id} not in cache, re-fetching events", xbmc.LOGINFO)
            self.get_events('all')  # Repopulate cache
            event = self._events_cache.get(event_id)
        
        if not event:
            xbmc.log(f"[Sportsfire] Event {event_id} not found after re-fetch", xbmc.LOGWARNING)
            return []
            
        streams = []
        
        for channel in event.get('channels', []):
            stream_encrypted = channel.get('stream_encrypted', '')
            
            if not stream_encrypted:
                continue
                
            # TODO: Decrypt stream URL
            # The http_stream field is encrypted using Security.convertHexToString + TokenURL
            # For now, we'll return it as-is with a note that decryption is pending
            
            stream_url = self._decrypt_stream(stream_encrypted)
            
            if stream_url:
                streams.append({
                    'name': channel.get('name', 'Unknown'),
                    'url': stream_url,
                    'quality': 'HD',
                    'language': channel.get('country', 'EN'),
                    'resolver': 'direct' if stream_url.endswith('.m3u8') else 'embed',
                })
            else:
                # Add placeholder for debugging
                streams.append({
                    'name': f"{channel.get('name', 'Unknown')} [ENCRYPTED]",
                    'url': f"encrypted://{stream_encrypted[:50]}...",
                    'quality': '?',
                    'language': channel.get('country', 'EN'),
                    'resolver': 'none',
                })
                
        xbmc.log(f"[Sportsfire] Found {len(streams)} streams for event {event_id}", xbmc.LOGINFO)
        return streams
        
    def _decrypt_stream(self, encrypted_b64: str) -> Optional[str]:
        """
        Decrypt a Sportsfire stream URL.
        
        NOTE: The Sportsfire APK uses a native library (libcompression.so) for encryption.
        The Crypt() function appears to use a custom cipher (not standard AES).
        
        From smali analysis:
        - Key: "ww23qq8811hh22aa" (16 chars)
        - Algorithm: Custom in native lib (_edCryption, make_SubKey, initKey patterns suggest DES-like)
        - Parameters include "nothing" strings which may affect key schedule
        
        Until the native algorithm is reversed, this function attempts common patterns.
        
        Args:
            encrypted_b64: Hex or Base64-encoded encrypted stream URL
            
        Returns:
            Decrypted URL or None if decryption fails
        """
        # Key extracted from APK (VideoPlayerActivity.smali line 72-74)
        DECRYPT_KEY = b"ww23qq8811hh22aa"  # 16 bytes
        
        if not encrypted_b64:
            return None
            
        # Decode input (hex or base64)
        try:
            # First try hex (the API returns hex-encoded data)
            try:
                ciphertext = bytes.fromhex(encrypted_b64)
            except ValueError:
                # Try base64
                import base64
                ciphertext = base64.b64decode(encrypted_b64)
        except Exception as e:
            xbmc.log(f"[Sportsfire] Failed to decode ciphertext: {e}", xbmc.LOGWARNING)
            return None
            
        # Try to import crypto library
        HAS_CRYPTO = False
        AES = None
        
        try:
            from Crypto.Cipher import AES as _AES
            AES = _AES
            HAS_CRYPTO = True
        except ImportError:
            try:
                from Cryptodome.Cipher import AES as _AES
                AES = _AES
                HAS_CRYPTO = True
            except ImportError:
                try:
                    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                    from cryptography.hazmat.backends import default_backend
                    HAS_CRYPTOGRAPHY = True
                except ImportError:
                    HAS_CRYPTOGRAPHY = False
                    
        # Attempt decryption with various algorithms
        attempts = []
        
        if HAS_CRYPTO and AES:
            # Try AES-ECB
            try:
                cipher = AES.new(DECRYPT_KEY, AES.MODE_ECB)
                plaintext = cipher.decrypt(ciphertext)
                plaintext = plaintext.rstrip(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
                url = plaintext.decode('utf-8', errors='ignore').strip()
                if url.startswith('http'):
                    return url
                attempts.append(('AES-ECB', url[:50] if len(url) > 50 else url))
            except Exception as e:
                attempts.append(('AES-ECB', str(e)))
                
            # Try AES-CBC with key as IV
            try:
                cipher = AES.new(DECRYPT_KEY, AES.MODE_CBC, iv=DECRYPT_KEY)
                plaintext = cipher.decrypt(ciphertext)
                plaintext = plaintext.rstrip(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
                url = plaintext.decode('utf-8', errors='ignore').strip()
                if url.startswith('http'):
                    return url
                attempts.append(('AES-CBC-key', url[:50] if len(url) > 50 else url))
            except Exception as e:
                attempts.append(('AES-CBC-key', str(e)))
                
        # Try simple XOR with key
        try:
            key_repeated = (DECRYPT_KEY * ((len(ciphertext) // len(DECRYPT_KEY)) + 1))[:len(ciphertext)]
            plaintext = bytes(a ^ b for a, b in zip(ciphertext, key_repeated))
            url = plaintext.decode('utf-8', errors='ignore').strip()
            if url.startswith('http'):
                return url
            attempts.append(('XOR', url[:50] if len(url) > 50 else url))
        except Exception as e:
            attempts.append(('XOR', str(e)))
            
        # Log attempts for debugging
        xbmc.log(f"[Sportsfire] Decryption failed. Input length: {len(ciphertext)} bytes", xbmc.LOGWARNING)
        xbmc.log(f"[Sportsfire] NOTE: Stream encryption uses native lib - algorithm not yet reversed", xbmc.LOGWARNING)
        for method, result in attempts:
            xbmc.log(f"[Sportsfire] {method}: {result}", xbmc.LOGDEBUG)
            
        return None
