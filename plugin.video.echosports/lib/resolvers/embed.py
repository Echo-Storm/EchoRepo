# -*- coding: utf-8 -*-
"""
Embed Resolver - Handle various embed player domains.

Based on patterns from plugin.video.sporthdme:
- dabac, sansat, istorm, zvision, glisco, bedsport
- coolrea, evfancy, s2watch, vuen, gopst

Updated March 2026: Added wilderness.click decryption
"""

import base64
import json
import math
import re
from typing import Optional, Dict
from urllib.parse import urlparse, urljoin, quote_plus

import requests
import xbmc


class EmbedResolver:
    """Resolver for embedded stream players."""
    
    # Known embed domains that require special handling
    SUPPORTED_DOMAINS = [
        'dabac', 'sansat', 'istorm', 'zvision', 'glisco',
        'bedsport', 'coolrea', 'evfancy', 's2watch', 'vuen', 'gopst',
        'wilderness', 'upstor'
    ]
    
    # Dead/broken embed domains - skip these entirely
    # Updated 2026-04-01: glisco.link timing out
    DEAD_DOMAINS = [
        'glisco.link',
    ]
    
    def __init__(self):
        self._session = requests.Session()
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self._last_referer = None
        
    def is_dead_domain(self, url: str) -> bool:
        """Check if URL uses a known dead/broken domain."""
        url_lower = url.lower()
        return any(dead in url_lower for dead in self.DEAD_DOMAINS)
        
    def can_resolve(self, url: str) -> bool:
        """Check if this resolver can handle the URL."""
        return any(domain in url.lower() for domain in self.SUPPORTED_DOMAINS)
        
    def resolve(self, url: str, referer: str = None) -> Optional[str]:
        """
        Resolve an embed URL to a playable stream.
        
        Args:
            url: Embed page URL
            referer: Optional referer URL
            
        Returns:
            Resolved m3u8/stream URL or None
        """
        if not url:
            return None
            
        # Ensure https
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
        
        # Check for dead domains - fail fast
        if self.is_dead_domain(url):
            xbmc.log(f"[EmbedResolver] Skipping dead domain: {url[:60]}", xbmc.LOGWARNING)
            return None
            
        self._last_referer = referer or self._extract_referer(url)
        
        xbmc.log(f"[EmbedResolver] Resolving: {url[:80]}", xbmc.LOGDEBUG)
        
        try:
            # First, fetch the embed page (reduced timeout from 15 to 8)
            headers = self._headers.copy()
            if self._last_referer:
                headers['Referer'] = self._last_referer
                
            response = self._session.get(url, headers=headers, timeout=8)
            response.raise_for_status()
            html = response.text
            
            # Try various extraction patterns
            stream_url = None
            
            # Pattern 1: API endpoint that returns JSON with URL
            if 'get_content.php?channel=' in html or 'api/player.php?id=' in html:
                stream_url = self._resolve_api_player(url, html)
                
            # Pattern 2: fid= script pattern
            elif 'fid=' in html:
                stream_url = self._resolve_fid_player(url, html)
                
            # Pattern 3: hlsjsConfig / data-page pattern
            elif 'hlsjsConfig' in html or 'data-page=' in html:
                stream_url = self._resolve_hlsjs_player(url, html)
                
            # Pattern 4: Clappr player
            elif 'new Clappr' in html:
                stream_url = self._resolve_clappr_player(url, html)
                
            # Pattern 5: player.setSrc
            elif 'player.setSrc' in html:
                stream_url = self._resolve_setsrc_player(html)
                
            # Pattern 6: Direct m3u8 in source
            else:
                stream_url = self._find_direct_m3u8(html)
                
            if stream_url:
                xbmc.log(f"[EmbedResolver] Found stream: {stream_url[:80]}", xbmc.LOGINFO)
                return stream_url
            else:
                xbmc.log(f"[EmbedResolver] No stream found in embed", xbmc.LOGWARNING)
                return None
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] Error: {e}", xbmc.LOGERROR)
            return None
            
    def _extract_referer(self, url: str) -> str:
        """Extract base URL for referer header."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/"
        
    def _resolve_api_player(self, url: str, html: str) -> Optional[str]:
        """Resolve API-based players (get_content.php, api/player.php)."""
        try:
            # Extract ID from URL
            match = re.search(r'(\d+)$', url)
            if not match:
                return None
            channel_id = match.group(1)
            
            base_url = self._extract_referer(url)
            
            # Try get_content.php
            if 'get_content.php' in html:
                api_url = urljoin(base_url, f"get_content.php?channel={channel_id}")
            else:
                api_url = urljoin(base_url, f"api/player.php?id={channel_id}")
                
            headers = self._headers.copy()
            headers['Referer'] = url
            
            response = self._session.get(api_url, headers=headers, timeout=8)
            data = response.text
            
            # Try to parse as JSON
            try:
                json_data = json.loads(data)
                if 'url' in json_data:
                    return self._follow_iframe(json_data['url'], url)
            except json.JSONDecodeError:
                pass
                
            # Try to find iframe
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)', data)
            if iframe_match:
                return self._follow_iframe(iframe_match.group(1), url)
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] API player error: {e}", xbmc.LOGDEBUG)
            
        return None
        
    def _resolve_fid_player(self, url: str, html: str) -> Optional[str]:
        """Resolve fid= script pattern players."""
        try:
            # Pattern: <script>fid="123"...src="embed.js"</script>
            match = re.search(r'<script>fid=[\'"](.+?)[\'"].+?src=[\'"](.+?)[\'"]', html, re.DOTALL)
            if not match:
                return None
                
            vid = match.group(1)
            embed_script_url = match.group(2)
            
            # Ensure absolute URL
            if embed_script_url.startswith('//'):
                embed_script_url = 'https:' + embed_script_url
                
            # Fetch the embed script
            headers = self._headers.copy()
            headers['Referer'] = url
            
            response = self._session.get(embed_script_url, headers=headers, timeout=8)
            embed_script = response.text
            
            # Find the player URL pattern
            match = re.search(r'document\.write.+?src=[\'"](.+?player)=', embed_script, re.DOTALL)
            if match:
                player_base = match.group(1)
                player_url = f"{player_base}=desktop&live={vid}"
                
                response = self._session.get(player_url, headers=headers, timeout=8)
                player_data = response.text
                
                # Extract stream URL
                return self._extract_stream_from_player(player_data)
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] fid player error: {e}", xbmc.LOGDEBUG)
            
        return None
        
    def _resolve_hlsjs_player(self, url: str, html: str) -> Optional[str]:
        """Resolve HLS.js based players."""
        try:
            # Try data-page attribute pattern
            match = re.search(r'data-page=[\'"]([^"\']+)', html)
            if match:
                data_page = match.group(1)
                # Unescape HTML entities
                data_page = data_page.replace('&quot;', '"').replace('\\/', '/')
                
                # Try to find m3u8 URL
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8)', data_page)
                if m3u8_match:
                    return m3u8_match.group(1)
                    
                # Try JSON parse
                try:
                    json_data = json.loads(data_page)
                    if 'props' in json_data:
                        stream_url = json_data.get('props', {}).get('streamData', {}).get('streamurl')
                        if stream_url:
                            return stream_url
                except json.JSONDecodeError:
                    pass
                    
            # Fallback: look for hlsUrl pattern
            match = re.search(r'hlsUrl\s*=\s*["\'](.+?)["\']', html)
            if match:
                return match.group(1)
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] HLS.js player error: {e}", xbmc.LOGDEBUG)
            
        return None
        
    def _resolve_clappr_player(self, url: str, html: str) -> Optional[str]:
        """Resolve Clappr-based players."""
        try:
            # Try simple source pattern
            match = re.search(r'source\s*:\s*["\']?(.+?)["\']?\s*[,}]', html)
            if match:
                source = match.group(1).strip()
                
                # If it's a direct URL
                if source.startswith('http') and '.m3u8' in source:
                    return source
                    
                # If it references a variable, we need more parsing
                if source in ['m3u8Url', 'm3u8', 'src']:
                    return self._resolve_clappr_advanced(url, html)
                    
            # Try file: pattern
            match = re.search(r'file\s*:\s*["\'](.+?)["\']', html)
            if match:
                return match.group(1)
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] Clappr player error: {e}", xbmc.LOGDEBUG)
            
        return None
        
    def _resolve_clappr_advanced(self, url: str, html: str) -> Optional[str]:
        """Resolve advanced Clappr players with CHANNEL_KEY/BUNDLE auth."""
        try:
            # Extract CHANNEL_KEY
            match = re.search(r'const\s+CHANNEL_KEY\s*=\s*["\']([^"\']+)', html)
            if not match:
                return None
            channel_key = match.group(1)
            
            # Extract BUNDLE
            match = re.search(r'const\s+BUNDLE\s*=\s*["\']([A-Za-z0-9+/=]+)["\']', html)
            if not match:
                return None
            bundle_b64 = match.group(1)
            
            # Decode bundle
            parts_raw = base64.b64decode(bundle_b64)
            parts = json.loads(parts_raw.decode('utf-8'))
            
            # Decode individual parts
            for key in parts:
                try:
                    parts[key] = base64.b64decode(parts[key]).decode('utf-8')
                except Exception:
                    pass
                    
            # Build auth URL
            auth_url = (
                parts.get('b_host', '') +
                parts.get('b_script', '') +
                '?channel_id=' + quote_plus(channel_key) +
                '&ts=' + quote_plus(parts.get('b_ts', '')) +
                '&rnd=' + quote_plus(parts.get('b_rnd', '')) +
                '&sig=' + quote_plus(parts.get('b_sig', ''))
            )
            
            # Make auth request
            headers = self._headers.copy()
            headers['Referer'] = url
            
            try:
                self._session.get(auth_url, headers=headers, timeout=5)
            except Exception:
                pass
                
            # Server lookup
            base_url = self._extract_referer(url)
            lookup_url = urljoin(base_url, f'/server_lookup.php?channel_id={quote_plus(channel_key)}')
            
            response = self._session.get(lookup_url, headers=headers, timeout=8)
            
            # Extract server_key
            try:
                json_resp = json.loads(response.text)
                server_key = json_resp.get('server_key', '').strip()
            except json.JSONDecodeError:
                match = re.search(r'"server_key"\s*:\s*"([^"]+)"', response.text)
                server_key = match.group(1).strip() if match else ''
                
            if not server_key:
                return None
                
            # Build stream URL
            sk_slug = server_key.strip('/')
            
            # Try common URL patterns
            candidates = [
                f'https://{sk_slug}.new.newkso.ru/{sk_slug}/{channel_key}/mono.m3u8',
                f'https://new.newkso.ru/{sk_slug}/{channel_key}/mono.m3u8',
            ]
            
            for candidate_url in candidates:
                try:
                    response = self._session.head(candidate_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        return candidate_url
                except Exception:
                    continue
                    
            return candidates[0]  # Return first as fallback
            
        except Exception as e:
            xbmc.log(f"[EmbedResolver] Clappr advanced error: {e}", xbmc.LOGDEBUG)
            
        return None
        
    def _resolve_setsrc_player(self, html: str) -> Optional[str]:
        """Resolve player.setSrc pattern."""
        match = re.search(r'player\.setSrc\(["\'](.+?)["\']', html)
        if match:
            return match.group(1)
        return None
        
    def _find_direct_m3u8(self, html: str) -> Optional[str]:
        """Find direct m3u8 URL in HTML."""
        # Look for m3u8 URLs
        matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if matches:
            return matches[0]
            
        # Look for source tag
        match = re.search(r'<source[^>]+src=["\']([^"\']+)', html)
        if match:
            return match.group(1)
            
        return None
        
    def _follow_iframe(self, iframe_url: str, referer: str) -> Optional[str]:
        """Follow an iframe URL and extract stream."""
        try:
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
                
            # Check if this is wilderness.click (or similar obfuscated player)
            if 'wilderness.click' in iframe_url:
                return self._resolve_wilderness(iframe_url, referer)
                
            headers = self._headers.copy()
            headers['Referer'] = referer
            
            response = self._session.get(iframe_url, headers=headers, timeout=8)
            html = response.text
            
            # Check if the response contains wilderness.click _econfig
            if 'window._econfig' in html:
                return self._resolve_wilderness_html(html, iframe_url)
            
            # Recursively try to extract
            return self._find_direct_m3u8(html) or self._extract_stream_from_player(html)
            
        except Exception as e:
            xbmc.log(f"[EmbedResolver] iframe follow error: {e}", xbmc.LOGDEBUG)
            
        return None
    
    def _resolve_wilderness(self, url: str, referer: str) -> Optional[str]:
        """Resolve wilderness.click obfuscated player."""
        try:
            headers = self._headers.copy()
            headers['Referer'] = referer
            
            response = self._session.get(url, headers=headers, timeout=8)
            return self._resolve_wilderness_html(response.text, url)
            
        except Exception as e:
            xbmc.log(f"[EmbedResolver] wilderness.click error: {e}", xbmc.LOGERROR)
            return None
    
    def _resolve_wilderness_html(self, html: str, referer: str) -> Optional[str]:
        """
        Decode wilderness.click obfuscated config.
        
        Algorithm (reverse-engineered from stream.js):
        1. Base64 decode the _econfig
        2. Split into 4 equal chunks
        3. Remove character at position 3 from each chunk
        4. Reorder chunks using [2, 0, 3, 1]
        5. Base64 decode each chunk
        6. Join all chunks
        7. Base64 decode again
        8. JSON.parse -> get stream_url
        """
        try:
            # Extract _econfig
            config_match = re.search(r"window\._econfig\s*=\s*['\"]([^'\"]+)['\"]", html)
            if not config_match:
                xbmc.log("[EmbedResolver] No _econfig found", xbmc.LOGWARNING)
                return None
                
            config = config_match.group(1)
            
            # Step 1: Base64 decode
            decoded = base64.b64decode(config).decode('utf-8')
            
            # Step 2: Split into 4 equal chunks
            chunk_count = 4
            chunk_size = math.ceil(len(decoded) / chunk_count)
            chunks = []
            pos = 0
            for i in range(chunk_count):
                chunk = decoded[pos:pos + chunk_size]
                chunks.append(chunk)
                pos += chunk_size
            
            # Step 3 & 4: Remove char at position 3, reorder using [2, 0, 3, 1]
            order = [2, 0, 3, 1]
            reordered = [None] * 4
            for i, chunk_idx in enumerate(order):
                modified = chunks[i]
                modified = modified[:3] + modified[4:]  # Remove char at index 3
                
                # Step 5: Base64 decode each chunk
                try:
                    decoded_chunk = base64.b64decode(modified).decode('utf-8')
                except Exception:
                    decoded_chunk = ""
                    
                reordered[chunk_idx] = decoded_chunk
            
            # Step 6: Join all chunks
            joined = ''.join(filter(None, reordered))
            
            # Step 7: Base64 decode again
            final = base64.b64decode(joined).decode('utf-8')
            
            # Step 8: JSON parse
            data = json.loads(final)
            
            # Get stream URL
            stream_url = data.get('stream_url') or data.get('stream_url_nop2p')
            
            if stream_url:
                xbmc.log(f"[EmbedResolver] wilderness.click decoded: {stream_url[:60]}...", xbmc.LOGINFO)
                self._last_referer = referer
                return stream_url
            else:
                xbmc.log(f"[EmbedResolver] No stream_url in wilderness config", xbmc.LOGWARNING)
                return None
                
        except Exception as e:
            xbmc.log(f"[EmbedResolver] wilderness decode error: {e}", xbmc.LOGERROR)
            return None
        
    def _extract_stream_from_player(self, html: str) -> Optional[str]:
        """Extract stream URL from player page content."""
        # Try return([...].join pattern
        match = re.search(r'return\s*\(\s*\[(.+?)\]\s*\.join', html, re.DOTALL)
        if match:
            try:
                array_content = match.group(1)
                # Parse the array
                parts = re.findall(r'["\']([^"\']*)["\']', array_content)
                url = ''.join(parts).replace('////', '//')
                if '.m3u8' in url or 'http' in url:
                    return url
            except Exception:
                pass
                
        # Try file: pattern
        match = re.search(r'file\s*:\s*["\'](.+?\.m3u8[^"\']*)["\']', html)
        if match:
            return match.group(1)
            
        return self._find_direct_m3u8(html)
        
    def get_headers(self) -> Dict[str, str]:
        """Get headers for playback."""
        headers = self._headers.copy()
        if self._last_referer:
            headers['Referer'] = self._last_referer
            headers['Origin'] = self._last_referer.rstrip('/')
        return headers
