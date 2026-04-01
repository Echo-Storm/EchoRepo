# -*- coding: utf-8 -*-
"""
Cache - Simple file-based caching for events.
"""

import json
import os
import time
from typing import Any, Optional

import xbmc
import xbmcaddon
import xbmcvfs


class Cache:
    """Simple file-based cache."""
    
    def __init__(self, cache_name: str = "events"):
        """
        Initialize cache.
        
        Args:
            cache_name: Name prefix for cache files
        """
        self.cache_name = cache_name
        addon = xbmcaddon.Addon()
        profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        
        # Ensure cache directory exists
        if not xbmcvfs.exists(profile_path):
            xbmcvfs.mkdirs(profile_path)
            
        self.cache_dir = profile_path
        
    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache key."""
        safe_key = key.replace('/', '_').replace(':', '_')
        return os.path.join(self.cache_dir, f"{self.cache_name}_{safe_key}.json")
        
    def get(self, key: str, max_age_seconds: int = 300) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            max_age_seconds: Maximum age in seconds before cache is stale
            
        Returns:
            Cached value or None if not found/expired
        """
        cache_path = self._get_cache_path(key)
        
        if not xbmcvfs.exists(cache_path):
            return None
            
        try:
            with xbmcvfs.File(cache_path, 'r') as f:
                data = json.loads(f.read())
                
            # Check expiry
            cached_time = data.get('_cached_at', 0)
            if time.time() - cached_time > max_age_seconds:
                xbmc.log(f"[Cache] Expired: {key}", xbmc.LOGDEBUG)
                return None
                
            return data.get('value')
            
        except Exception as e:
            xbmc.log(f"[Cache] Read error: {e}", xbmc.LOGWARNING)
            return None
            
    def set(self, key: str, value: Any) -> bool:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            
        Returns:
            True if successful
        """
        cache_path = self._get_cache_path(key)
        
        try:
            data = {
                '_cached_at': time.time(),
                'value': value,
            }
            
            with xbmcvfs.File(cache_path, 'w') as f:
                f.write(json.dumps(data))
                
            return True
            
        except Exception as e:
            xbmc.log(f"[Cache] Write error: {e}", xbmc.LOGWARNING)
            return False
            
    def clear(self, key: str = None) -> bool:
        """
        Clear cache.
        
        Args:
            key: Specific key to clear, or None to clear all
            
        Returns:
            True if successful
        """
        try:
            if key:
                cache_path = self._get_cache_path(key)
                if xbmcvfs.exists(cache_path):
                    xbmcvfs.delete(cache_path)
            else:
                # Clear all cache files
                dirs, files = xbmcvfs.listdir(self.cache_dir)
                for f in files:
                    if f.startswith(f"{self.cache_name}_") and f.endswith('.json'):
                        xbmcvfs.delete(os.path.join(self.cache_dir, f))
                        
            return True
            
        except Exception as e:
            xbmc.log(f"[Cache] Clear error: {e}", xbmc.LOGWARNING)
            return False
