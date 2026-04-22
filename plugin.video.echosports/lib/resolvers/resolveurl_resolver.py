# -*- coding: utf-8 -*-
"""
ResolveURL Resolver - Stream resolution via ResolveURL addon.

ResolveURL handles:
- Debrid services: Real-Debrid, Premiumize, AllDebrid
- File hosters: dood, streamtape, vidoza, mixdrop, etc.
- Video sites: various streaming platforms

This replaces the custom Real-Debrid implementation with the standard
community-maintained ResolveURL addon.
"""

from typing import Optional, Dict
import xbmc


class ResolveURLResolver:
    """
    Resolver using the ResolveURL Kodi addon.
    
    ResolveURL is the community standard for resolving video URLs
    and integrating with debrid services.
    """
    
    def __init__(self):
        self._resolveurl = None
        self._available = None
        self._last_headers = {}
        
    def _get_resolveurl(self):
        """Lazy load ResolveURL to avoid import errors if not installed."""
        if self._resolveurl is None:
            try:
                import resolveurl
                self._resolveurl = resolveurl
                self._available = True
                xbmc.log("[ResolveURL] Module loaded successfully", xbmc.LOGDEBUG)
            except ImportError:
                self._available = False
                xbmc.log("[ResolveURL] Module not available - install script.module.resolveurl", xbmc.LOGWARNING)
        return self._resolveurl
    
    def is_available(self) -> bool:
        """Check if ResolveURL is installed and available."""
        if self._available is None:
            self._get_resolveurl()
        return self._available
    
    def can_resolve(self, url: str) -> bool:
        """
        Check if ResolveURL can handle this URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if ResolveURL reports it can handle this URL
        """
        resolveurl = self._get_resolveurl()
        if not resolveurl:
            return False
            
        try:
            hmf = resolveurl.HostedMediaFile(url=url)
            return hmf.valid_url()
        except Exception as e:
            xbmc.log(f"[ResolveURL] can_resolve error: {e}", xbmc.LOGDEBUG)
            return False
    
    def resolve(self, url: str) -> Optional[str]:
        """
        Resolve a URL via ResolveURL.
        
        This will:
        1. Check if ResolveURL recognizes the URL
        2. Use configured debrid service if available
        3. Fall back to free resolver if no debrid
        
        Args:
            url: URL to resolve
            
        Returns:
            Direct playable URL or None on failure
        """
        resolveurl = self._get_resolveurl()
        if not resolveurl:
            xbmc.log("[ResolveURL] Not available", xbmc.LOGWARNING)
            return None
        
        # Log URL type for debugging
        is_magnet = url.startswith('magnet:')
        xbmc.log(f"[ResolveURL] Resolving (magnet={is_magnet}): {url[:100]}", xbmc.LOGINFO)
        
        try:
            hmf = resolveurl.HostedMediaFile(url=url)
            
            valid = hmf.valid_url()
            xbmc.log(f"[ResolveURL] valid_url() returned: {valid}", xbmc.LOGINFO)
            
            if not valid:
                xbmc.log(f"[ResolveURL] URL not recognized by any resolver", xbmc.LOGWARNING)
                return None
            
            xbmc.log(f"[ResolveURL] Calling hmf.resolve()...", xbmc.LOGINFO)
            resolved = hmf.resolve()
            
            if resolved:
                xbmc.log(f"[ResolveURL] Resolved successfully: {resolved[:80]}", xbmc.LOGINFO)
                return resolved
            else:
                xbmc.log(f"[ResolveURL] hmf.resolve() returned empty/None", xbmc.LOGWARNING)
                return None
                
        except Exception as e:
            error_str = str(e)
            xbmc.log(f"[ResolveURL] Error: {type(e).__name__}: {e}", xbmc.LOGERROR)
            
            # Check for specific error types
            if '404' in error_str or 'Unavailable' in error_str:
                xbmc.log("[ResolveURL] File appears to be dead/removed (404)", xbmc.LOGWARNING)
                self._last_error = 'dead_link'
            elif 'token' in error_str.lower() or 'auth' in error_str.lower():
                xbmc.log("[ResolveURL] Authentication error - may need re-auth", xbmc.LOGWARNING)
                self._last_error = 'auth_error'
            else:
                self._last_error = 'unknown'
            
            import traceback
            xbmc.log(f"[ResolveURL] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
            return None
    
    def get_last_error(self) -> str:
        """Get the last error type for better error messages."""
        return getattr(self, '_last_error', 'unknown')
    
    def resolve_with_debrid_priority(self, url: str) -> Optional[str]:
        """
        Resolve with explicit debrid preference.
        
        ResolveURL automatically uses debrid if configured,
        but this method is here for API compatibility.
        """
        return self.resolve(url)
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for playback.
        
        ResolveURL typically handles headers internally,
        but we provide safe defaults.
        """
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
    
    def open_settings(self):
        """Open ResolveURL settings dialog."""
        resolveurl = self._get_resolveurl()
        if resolveurl:
            try:
                resolveurl.display_settings()
            except Exception as e:
                xbmc.log(f"[ResolveURL] Failed to open settings: {e}", xbmc.LOGERROR)
    
    def check_debrid_status(self) -> dict:
        """
        Check status of debrid services in ResolveURL.
        
        Returns dict with service names and their status.
        """
        status = {
            'available': False,
            'real_debrid': False,
            'premiumize': False,
            'all_debrid': False,
            'error': None
        }
        
        resolveurl = self._get_resolveurl()
        if not resolveurl:
            status['error'] = 'ResolveURL not installed'
            return status
        
        status['available'] = True
        
        try:
            # Try to check if debrid resolvers are enabled
            # ResolveURL stores this in Kodi settings
            import xbmcaddon
            ru_addon = xbmcaddon.Addon('script.module.resolveurl')
            
            # Check Real-Debrid
            rd_enabled = ru_addon.getSetting('RealDebridResolver_enabled')
            rd_token = ru_addon.getSetting('RealDebridResolver_token')
            status['real_debrid'] = rd_enabled == 'true' and bool(rd_token)
            
            # Check Premiumize
            pm_enabled = ru_addon.getSetting('PremiumizeMeResolver_enabled')
            pm_token = ru_addon.getSetting('PremiumizeMeResolver_token')
            status['premiumize'] = pm_enabled == 'true' and bool(pm_token)
            
            # Check AllDebrid
            ad_enabled = ru_addon.getSetting('AllDebridResolver_enabled')
            ad_token = ru_addon.getSetting('AllDebridResolver_token')
            status['all_debrid'] = ad_enabled == 'true' and bool(ad_token)
            
            xbmc.log(f"[ResolveURL] Debrid status: RD={status['real_debrid']}, PM={status['premiumize']}, AD={status['all_debrid']}", xbmc.LOGINFO)
            
        except Exception as e:
            status['error'] = str(e)
            xbmc.log(f"[ResolveURL] Error checking debrid status: {e}", xbmc.LOGWARNING)
        
        return status


# Singleton instance for reuse
_resolver_instance = None


def get_resolver() -> ResolveURLResolver:
    """Get shared resolver instance."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ResolveURLResolver()
    return _resolver_instance


def is_available() -> bool:
    """Check if ResolveURL is available."""
    return get_resolver().is_available()


def can_resolve(url: str) -> bool:
    """Check if URL can be resolved."""
    return get_resolver().can_resolve(url)


def resolve(url: str) -> Optional[str]:
    """Resolve a URL."""
    return get_resolver().resolve(url)
