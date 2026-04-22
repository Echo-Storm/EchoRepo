# -*- coding: utf-8 -*-
"""
yt-dlp Resolver - Extract playable streams from various hosting sites.

Resolution order:
1. System yt-dlp (if in PATH) via subprocess
2. ResolveURL (if installed)
3. Fail gracefully

This does NOT require the broken script.module.yt-dlp addon.
If you want yt-dlp support, install it system-wide:
  pip install yt-dlp
  (or your package manager's version)
"""

import json
import subprocess
import shutil
from typing import Optional, Dict, Tuple
import xbmc


class YTDLPResolver:
    """Resolver using system yt-dlp or ResolveURL fallback."""
    
    # Domains known to work well with yt-dlp
    SUPPORTED_DOMAINS = [
        'mail.ru', 'my.mail.ru',
        'dood.la', 'dood.wf', 'dood.pm', 'dood.to', 'dood.watch', 'doodstream',
        'luluvdo.com', 'luluvid.com',  # FOD non-debrid hosters
        'streamtape.com', 'streamtape.to',
        'vk.com', 'vk.ru',
        'dailymotion.com',
        'ok.ru',
        'rutube.ru',
        'youtube.com', 'youtu.be',
        'facebook.com', 'fb.watch',
        'twitter.com', 'x.com',
        'twitch.tv',
        'vimeo.com',
        'streamable.com',
        'vidoza.net',
        'mixdrop.co', 'mixdrop.to',
        'upstream.to',
        'voe.sx',
        'filemoon.sx',
        'streamwish.to',
        'vidhide.com',
        'mp4upload.com',
        'uqload.com',
    ]
    
    def __init__(self):
        self._ytdlp_path = None
        self._ytdlp_checked = False
        self._last_headers = {}
        
    def _find_ytdlp(self) -> Optional[str]:
        """Find yt-dlp binary in system PATH."""
        if not self._ytdlp_checked:
            self._ytdlp_checked = True
            
            # Check common names
            for name in ['yt-dlp', 'yt_dlp', 'youtube-dl']:
                path = shutil.which(name)
                if path:
                    xbmc.log(f"[YTDLPResolver] Found system {name} at: {path}", xbmc.LOGINFO)
                    self._ytdlp_path = path
                    break
                    
            if not self._ytdlp_path:
                xbmc.log("[YTDLPResolver] No system yt-dlp found in PATH", xbmc.LOGDEBUG)
                
        return self._ytdlp_path
        
    def can_resolve(self, url: str) -> bool:
        """Check if this resolver can handle the URL."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.SUPPORTED_DOMAINS)
    
    def _resolve_via_subprocess(self, url: str) -> Optional[str]:
        """
        Resolve URL using system yt-dlp via subprocess.
        
        This is safer and more reliable than importing a Kodi addon.
        """
        ytdlp_path = self._find_ytdlp()
        if not ytdlp_path:
            return None
            
        try:
            # Run yt-dlp with JSON output
            cmd = [
                ytdlp_path,
                '--no-warnings',
                '--no-playlist',
                '--format', 'best[ext=mp4]/best',
                '--dump-json',
                '--geo-bypass',
                '--no-check-certificate',
                url
            ]
            
            xbmc.log(f"[YTDLPResolver] Running: {' '.join(cmd[:3])}...", xbmc.LOGDEBUG)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                xbmc.log(f"[YTDLPResolver] Subprocess failed: {result.stderr[:200]}", xbmc.LOGWARNING)
                return None
                
            # Parse JSON output
            info = json.loads(result.stdout)
            
            # Extract URL
            stream_url = None
            self._last_headers = {}
            
            # Direct URL
            if info.get('url'):
                stream_url = info['url']
                self._last_headers = info.get('http_headers', {})
                
            # From formats list
            elif info.get('formats'):
                formats = info['formats']
                
                # Prefer mp4 with highest quality
                mp4_formats = [f for f in formats if f.get('ext') == 'mp4' and f.get('url')]
                if mp4_formats:
                    mp4_formats.sort(key=lambda x: (x.get('height') or 0, x.get('tbr') or 0))
                    best = mp4_formats[-1]
                    stream_url = best['url']
                    self._last_headers = best.get('http_headers', {})
                elif formats:
                    for f in reversed(formats):
                        if f.get('url'):
                            stream_url = f['url']
                            self._last_headers = f.get('http_headers', {})
                            break
            
            if stream_url:
                xbmc.log(f"[YTDLPResolver] Subprocess resolved: {stream_url[:60]}...", xbmc.LOGINFO)
                
            return stream_url
            
        except subprocess.TimeoutExpired:
            xbmc.log("[YTDLPResolver] Subprocess timed out", xbmc.LOGWARNING)
            return None
        except json.JSONDecodeError as e:
            xbmc.log(f"[YTDLPResolver] JSON parse error: {e}", xbmc.LOGWARNING)
            return None
        except Exception as e:
            xbmc.log(f"[YTDLPResolver] Subprocess error: {type(e).__name__}: {e}", xbmc.LOGERROR)
            return None
    
    def _resolve_via_resolveurl(self, url: str) -> Optional[str]:
        """Fallback to ResolveURL if yt-dlp not available."""
        try:
            from lib.resolvers.resolveurl_resolver import resolve
            resolved = resolve(url)
            if resolved:
                xbmc.log(f"[YTDLPResolver] ResolveURL fallback: {resolved[:60]}...", xbmc.LOGINFO)
            return resolved
        except ImportError:
            xbmc.log("[YTDLPResolver] ResolveURL not available", xbmc.LOGDEBUG)
            return None
        except Exception as e:
            xbmc.log(f"[YTDLPResolver] ResolveURL error: {e}", xbmc.LOGDEBUG)
            return None
        
    def resolve(self, url: str) -> Optional[str]:
        """
        Resolve a URL to a direct stream.
        
        Resolution order:
        1. System yt-dlp via subprocess
        2. ResolveURL fallback
        
        Args:
            url: Page URL containing video
            
        Returns:
            Direct stream URL or None
        """
        if not url:
            return None
            
        xbmc.log(f"[YTDLPResolver] Resolving: {url[:80]}", xbmc.LOGDEBUG)
        
        # Try system yt-dlp first
        resolved = self._resolve_via_subprocess(url)
        if resolved:
            return resolved
            
        # Fallback to ResolveURL
        resolved = self._resolve_via_resolveurl(url)
        if resolved:
            return resolved
            
        xbmc.log(f"[YTDLPResolver] All methods failed for: {url[:50]}", xbmc.LOGWARNING)
        return None
        
    def resolve_with_headers(self, url: str) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Resolve URL and return headers needed for playback.
        
        Args:
            url: Page URL
            
        Returns:
            Tuple of (stream_url, headers_dict)
        """
        self._last_headers = {}
        stream_url = self.resolve(url)
        return stream_url, self._last_headers.copy()
        
    def get_headers(self) -> Dict[str, str]:
        """Get headers from last resolution."""
        return self._last_headers.copy()


# Singleton instance for reuse
_resolver_instance = None


def get_resolver() -> YTDLPResolver:
    """Get shared resolver instance."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = YTDLPResolver()
    return _resolver_instance


def resolve(url: str) -> Optional[str]:
    """Convenience function to resolve a URL."""
    return get_resolver().resolve(url)


def resolve_with_headers(url: str) -> Tuple[Optional[str], Dict[str, str]]:
    """Convenience function to resolve with headers."""
    return get_resolver().resolve_with_headers(url)
