# -*- coding: utf-8 -*-
"""
NFL Rewind Content Source for plugin.video.echosports

Parses NFL game replays from mylostsoulspace.co.uk feeds.
Uses same XML format as FOD (Fights on Demand).
"""

import re
import xbmc

try:
    import requests
except ImportError:
    requests = None

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import Request, urlopen, URLError


class NFLContentSource:
    """
    NFL Rewind content source.
    
    Feed structure:
    - Main menu lists seasons
    - Each season has weeks + playoffs
    - Each week/playoff has games
    - Each game has multiple stream versions (full, condensed, with/without ads)
    """
    
    BASE_URL = 'https://mylostsoulspace.co.uk/NFLRewind'
    
    # Feed URLs
    FEEDS = {
        'main': f'{BASE_URL}/xmls/MainXml/nflrewind-main.xml',
        
        # 25/26 Season
        'season_25': f'{BASE_URL}/xmls/25-26/nflreplaysmain25.xml',
        'superbowl_25': f'{BASE_URL}/xmls/25-26/nflreplayssuperbowl-25.xml',
        'probowl_25': f'{BASE_URL}/xmls/25-26/nflreplaysprobowl-25.xml',
        'conference_25': f'{BASE_URL}/xmls/25-26/nflreplaysconference-25.xml',
        'divisional_25': f'{BASE_URL}/xmls/25-26/nflreplaysdivisional-25.xml',
        'wildcard_25': f'{BASE_URL}/xmls/25-26/nflreplayswildcard-25.xml',
        
        # 24/25 Season
        'season_24': f'{BASE_URL}/xmls/24-25/nflreplaysmain24.xml',
        
        # 23/24 Season (note: same path as 24/25)
        'season_23': f'{BASE_URL}/xmls/23-24/nflreplaysmain23.xml',
    }
    
    # Default artwork
    DEFAULT_ICON = f'{BASE_URL}/art/icon.png'
    DEFAULT_FANART = f'{BASE_URL}/art/fanart.jpg'
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/xml, application/xml, */*',
        }
        # Use requests session like FOD does
        if requests:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        else:
            self.session = None
    
    def _fetch_url(self, url, timeout=15):
        """Fetch content from URL using requests (like FOD)."""
        try:
            xbmc.log(f"[NFL] Fetching URL: {url}", xbmc.LOGINFO)
            
            if self.session:
                # Use requests like FOD does
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                content = response.text
            else:
                # Fallback to urllib
                req = Request(url, headers=self.headers)
                response = urlopen(req, timeout=timeout)
                content = response.read().decode('utf-8', errors='replace')
            
            xbmc.log(f"[NFL] Fetched {len(content)} bytes", xbmc.LOGINFO)
            return content
        except Exception as e:
            xbmc.log(f"[NFL] Error fetching {url}: {e}", xbmc.LOGERROR)
            return None
    
    def _parse_xml(self, content):
        """
        Parse XML content and extract items.
        
        Returns list of dicts with keys:
        - type: 'dir' or 'item'
        - title: Display title
        - link: URL or magnet(s)
        - thumbnail, fanart, summary
        """
        if not content:
            xbmc.log("[NFL] No content to parse", xbmc.LOGWARNING)
            return []
        
        items = []
        
        # Normalize line endings (Windows CRLF -> LF)
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Log a sample for debugging
        xbmc.log(f"[NFL] Content sample: {content[100:300]}", xbmc.LOGDEBUG)
        
        # Parse directories - simpler pattern without \s*
        # Using re.S (same as DOTALL) for explicit flag
        dir_pattern = r'<dir>(.*?)</dir>'
        dir_matches = re.findall(dir_pattern, content, re.S)
        xbmc.log(f"[NFL] Found {len(dir_matches)} dir blocks", xbmc.LOGINFO)
        
        for block in dir_matches:
            item = self._parse_block(block.strip(), 'dir')
            if item:
                items.append(item)
        
        # Parse items
        item_pattern = r'<item>(.*?)</item>'
        item_matches = re.findall(item_pattern, content, re.S)
        xbmc.log(f"[NFL] Found {len(item_matches)} item blocks", xbmc.LOGINFO)
        
        for block in item_matches:
            item = self._parse_block(block.strip(), 'item')
            if item:
                items.append(item)
        
        xbmc.log(f"[NFL] Parsed {len(items)} total items", xbmc.LOGINFO)
        return items
    
    def _parse_block(self, block, item_type):
        """Parse a single <dir> or <item> block."""
        def extract(pattern, text, default=''):
            m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else default
        
        title = extract(r'<title>(.*?)</title>', block)
        if not title:
            return None
        
        # Clean Kodi color tags for comparison but keep for display
        title_clean = re.sub(r'\[/?COLOR[^\]]*\]', '', title)
        
        item = {
            'type': item_type,
            'title': title,
            'title_clean': title_clean,
            'thumbnail': extract(r'<thumbnail>(.*?)</thumbnail>', block) or self.DEFAULT_ICON,
            'fanart': extract(r'<fanart>(.*?)</fanart>', block) or self.DEFAULT_FANART,
            'summary': extract(r'<summary>(.*?)</summary>', block),
        }
        
        # Parse link(s)
        link_block = extract(r'<link>(.*?)</link>', block)
        
        if item_type == 'dir':
            # Directory - single URL
            item['link'] = link_block.strip() if link_block else ''
        else:
            # Item - may have multiple sublinks
            sublinks = re.findall(r'<sublink>(.*?)</sublink>', link_block, re.DOTALL)
            if sublinks:
                item['links'] = []
                for sl in sublinks:
                    sl = sl.strip()
                    # Extract label from parentheses if present
                    label_match = re.search(r'\(([^)]+)\)\s*$', sl)
                    if label_match:
                        label = label_match.group(1)
                        url = sl[:label_match.start()].strip()
                    else:
                        label = None
                        url = sl
                    
                    item['links'].append({
                        'url': url,
                        'label': label,
                    })
            elif link_block.strip():
                # Single link
                item['links'] = [{'url': link_block.strip(), 'label': None}]
            else:
                item['links'] = []
        
        return item
    
    def _fetch_and_parse(self, url):
        """Fetch URL and parse XML content."""
        content = self._fetch_url(url)
        return self._parse_xml(content) if content else []
    
    # === Public API ===
    
    def get_seasons(self):
        """Get list of available seasons."""
        return self._fetch_and_parse(self.FEEDS['main'])
    
    def get_current_season(self):
        """Get current (25/26) season menu."""
        return self._fetch_and_parse(self.FEEDS['season_25'])
    
    def get_season_24(self):
        """Get 24/25 season menu."""
        return self._fetch_and_parse(self.FEEDS['season_24'])
    
    def get_season_23(self):
        """Get 23/24 season menu."""
        return self._fetch_and_parse(self.FEEDS['season_23'])
    
    def get_superbowl(self):
        """Get Super Bowl games."""
        return self._fetch_and_parse(self.FEEDS['superbowl_25'])
    
    def get_probowl(self):
        """Get Pro Bowl games."""
        return self._fetch_and_parse(self.FEEDS['probowl_25'])
    
    def get_conference(self):
        """Get Conference Championship games."""
        return self._fetch_and_parse(self.FEEDS['conference_25'])
    
    def get_divisional(self):
        """Get Divisional Round games."""
        return self._fetch_and_parse(self.FEEDS['divisional_25'])
    
    def get_wildcard(self):
        """Get Wildcard Round games."""
        return self._fetch_and_parse(self.FEEDS['wildcard_25'])
    
    def get_content_from_url(self, url):
        """Fetch and parse any XML URL (for dynamic navigation)."""
        return self._fetch_and_parse(url)
    
    def format_items(self, items, category=''):
        """
        Format items for display in Kodi.
        
        For items with links, sets up primary_link for playback.
        """
        formatted = []
        
        for item in items:
            if item['type'] == 'dir':
                formatted.append({
                    'type': 'dir',
                    'title': item['title'],
                    'xml_url': item.get('link', ''),
                    'thumbnail': item.get('thumbnail'),
                    'fanart': item.get('fanart'),
                    'summary': item.get('summary', ''),
                })
            elif item['type'] == 'item':
                links = item.get('links', [])
                if links:
                    formatted.append({
                        'type': 'item',
                        'title': item['title'],
                        'links': links,
                        'primary_link': links[0],
                        'thumbnail': item.get('thumbnail'),
                        'fanart': item.get('fanart'),
                        'summary': item.get('summary', ''),
                    })
        
        return formatted
