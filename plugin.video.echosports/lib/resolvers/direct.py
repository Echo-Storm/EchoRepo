# -*- coding: utf-8 -*-
"""
Direct URL Resolver - for M3U8 and direct video URLs
"""

import xbmc


class DirectResolver:
    """
    Simple resolver for direct playable URLs (M3U8, MP4, etc.)
    
    These URLs don't need resolving - they're ready to play.
    Just returns the URL as-is with optional headers.
    """
    
    def __init__(self):
        self.name = "Direct"
    
    def resolve(self, url, headers=None):
        """
        'Resolve' a direct URL (just return it as-is).
        
        Args:
            url: Direct playable URL (M3U8, MP4, etc.)
            headers: Optional dict of HTTP headers for playback
            
        Returns:
            dict with 'url' and optional 'headers'
        """
        xbmc.log(f"[DirectResolver] Passing through direct URL: {url[:100]}...", xbmc.LOGDEBUG)
        
        result = {'url': url}
        
        # Include headers if provided
        if headers:
            result['headers'] = headers
            
        return result
