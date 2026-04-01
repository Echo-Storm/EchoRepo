# -*- coding: utf-8 -*-
"""
Direct Resolver - Handle direct HLS/m3u8 streams.
"""

from typing import Optional, Dict
import xbmc


class DirectResolver:
    """Resolver for direct HLS streams."""
    
    def __init__(self):
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        self._last_referer = None
        
    def resolve(self, url: str, referer: str = None) -> Optional[str]:
        """
        Resolve a stream URL.
        
        For direct streams, this mainly validates and formats the URL.
        
        Args:
            url: Stream URL
            referer: Optional referer URL
            
        Returns:
            Resolved playable URL or None
        """
        if not url:
            return None
            
        # Skip encrypted URLs
        if url.startswith('encrypted://'):
            xbmc.log(f"[DirectResolver] Encrypted URL cannot be resolved: {url[:50]}", xbmc.LOGWARNING)
            return None
            
        # Handle protocol prefix
        if url.startswith('ffmpegdirect://'):
            url = url.replace('ffmpegdirect://', '')
            
        # Ensure https
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
            
        # Store referer for headers
        if referer:
            self._last_referer = referer
        else:
            # Extract domain as referer
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                self._last_referer = f"{parsed.scheme}://{parsed.netloc}/"
            except Exception:
                self._last_referer = None
                
        xbmc.log(f"[DirectResolver] Resolved: {url[:80]}...", xbmc.LOGDEBUG)
        return url
        
    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for playback.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = self._headers.copy()
        
        if self._last_referer:
            headers['Referer'] = self._last_referer
            headers['Origin'] = self._last_referer.rstrip('/')
            
        return headers
